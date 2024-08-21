import json
import os
from collections.abc import AsyncGenerator, Hashable, Sequence
from typing import Any, Dict, Literal, Protocol  # noqa UP

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.output_parsers.openai_functions import JsonOutputFunctionsParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langfuse.callback import CallbackHandler
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.constants import END, START
from langgraph.graph import MessagesState, StateGraph
from langgraph.graph.graph import CompiledGraph

from agents.common.data import Message
from agents.common.state import AgentState, Plan, SubTask
from agents.k8s.agent import K8S_AGENT, k8s_agent_node
from agents.kyma.agent import KYMA_AGENT, kyma_agent_node
from utils.logging import get_logger
from utils.models import Model

PLANNER = "Planner"
SUPERVISOR = "Supervisor"
FINALIZER = "Finalize"

logger = get_logger(__name__)

langfuse_handler = CallbackHandler(
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    host=os.getenv("LANGFUSE_HOST"),
)


def should_continue(state: MessagesState) -> Literal["action", "__end__"]:
    """Return the next node to execute."""
    last_message = state["messages"][-1]
    return "action" if last_message.tool_calls else "__end__"


def filter_messages(
    messages: Sequence[BaseMessage], last_messages_number: int = 10
) -> Sequence[BaseMessage]:
    """This is very simple helper function which only ever uses the last four messages"""
    return messages[-last_messages_number:]


class Agent(Protocol):
    """Agent interface."""

    async def astream(
        self, conversation_id: int, message: Message
    ) -> AsyncGenerator[dict, None]:
        """Stream the input to the supervisor asynchronously."""
        ...


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder."""

    def default(self, obj):  # noqa D102
        if isinstance(obj, AIMessage | HumanMessage | SubTask):
            return obj.__dict__
        return super().default(obj)


class SupervisorAgent:
    """Supervisor agent class."""

    model: Model
    memory: BaseCheckpointSaver
    kyma_agent = None
    tools = None
    members = [KYMA_AGENT, K8S_AGENT]

    parser = PydanticOutputParser(pydantic_object=Plan)  # type: ignore

    def __init__(self, model: Model, memory: BaseCheckpointSaver):
        self.model = model
        self.memory = memory

        options: list[str] = [FINALIZER] + self.members
        function_def = {
            "name": "assign_and_route",
            "description": "Assign subtasks to agents.",
            "parameters": {
                "type": "object",
                "properties": {
                    "subtasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "assigned_to": {"enum": options},
                            },
                            "required": ["description", "assigned_to"],
                        },
                    },
                    "next": {"type": "string", "enum": options},
                },
                "required": ["subtasks", "next"],
            },
        }

        supervisor_system_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a supervisor tasked with managing a conversation between the agents: {members}.\n"
                    "Given the subtasks, assign each subtask to an appropriate agent, "
                    "and supervise conversation between the agents to a achieve the goal given in the query. "
                    "You also decide when the work should be finalized. When all subtasks are completed, "
                    f"respond with {FINALIZER}. ",
                ),
                MessagesPlaceholder(variable_name="messages"),
                (
                    "system",
                    "Given the conversation above, who should act next? "
                    "Or should we finalize? Select one of: {options}\n"
                    f"Set {FINALIZER} if only if all the subtasks statuses are 'completed'.",
                ),
            ]
        ).partial(options=str(options), members=", ".join(options))

        self.supervisor_chain = (
            supervisor_system_prompt
            | model.llm.bind_functions(
                functions=[function_def], function_call="assign_and_route"
            )
            | JsonOutputFunctionsParser()
        )

        self.graph = self._build_graph()

    def _plan(self, state: AgentState) -> dict[str, Any]:
        """Breaks down the given user query into sub-tasks."""
        planner_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "For the given query, come up with a simple step by step plan. "
                    "Each step/subtask should be assigned to one of these agents: {members}.\n"
                    "This plan should involve individual subtasks, that if executed correctly will yield "
                    "the correct answer. Do not add any superfluous steps."
                    "The result of the final step should be the final answer. "
                    "Make sure that each step has all the information needed - do not skip steps.\n"
                    "{output_format}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        ).partial(
            members=", ".join(self.members),
            output_format=self.parser.get_format_instructions(),
        )
        planner = planner_prompt | self.model.llm
        try:
            plan = planner.invoke(
                {
                    "messages": state.messages[-1:],
                },  # last message is the user query
                config={"callbacks": [langfuse_handler]},
            )
            state.subtasks = self.parser.parse(plan.content).subtasks
            return {
                "subtasks": state.subtasks,
                "messages": (
                    [
                        AIMessage(
                            content=f"Task decomposed into subtasks and assigned to agents: {state.subtasks}",
                            name=PLANNER,
                        )
                    ]
                ),
            }
        except Exception as e:
            logger.error(f"Error in planning: {e}")
            return {
                "messages": [
                    AIMessage(
                        content=f"Error in planning: {e}",
                        name="Planner",
                    )
                ],
            }

    def generate_final_response(self, state: AgentState) -> dict[str, Any]:
        """Generate the final response."""

        state.messages = filter_messages(state.messages)

        prompt = ChatPromptTemplate.from_messages(
            [
                MessagesPlaceholder(variable_name="messages"),
                (
                    "system",
                    "You are Kyma, Kubernetes and SAP Business Technology Platform expert. "
                    "Generate a final comprehensive response based on the responses of the {members} agents.",
                ),
            ]
        ).partial(members=", ".join(self.members))

        final_response_chain = prompt | self.model.llm
        state.final_response = final_response_chain.invoke(
            {"messages": [m for m in state.messages if m.name in self.members]},
            config={"callbacks": [langfuse_handler]},
        ).content

        return {
            "final_response": state.final_response,
            "messages": [
                AIMessage(
                    content=state.final_response,
                    name="Finalize",
                )
            ],
            "next": END,
        }

    def supervisor_node(self, state: AgentState) -> dict[str, Any]:
        """Supervisor node."""
        result = self.supervisor_chain.invoke(
            state.dict()
        )  # langchain needs pydantic v1

        return {
            "next": result["next"],
            "subtasks": state.subtasks,
        }

    def _build_graph(self) -> CompiledGraph:
        """Create a supervisor agent."""

        workflow = StateGraph(AgentState)
        workflow.add_node(FINALIZER, self.generate_final_response)
        workflow.add_node(KYMA_AGENT, kyma_agent_node)
        workflow.add_node(K8S_AGENT, k8s_agent_node)
        workflow.add_node(SUPERVISOR, self.supervisor_node)
        workflow.add_node(PLANNER, self._plan)

        # pass the subtasks to supervisor to route to agents
        workflow.add_edge(PLANNER, SUPERVISOR)
        for member in self.members:
            # We want our workers to ALWAYS "report back" to the supervisor when done
            workflow.add_edge(member, SUPERVISOR)
        # The supervisor populates the "next" field in the graph state
        # which routes to a node or finishes
        conditional_map: dict[Hashable, str] = {
            k: k for k in self.members + [FINALIZER]
        }
        workflow.add_conditional_edges(SUPERVISOR, lambda x: x.next, conditional_map)
        # Add end node
        workflow.add_edge(FINALIZER, END)
        # Add entrypoint
        workflow.add_edge(START, PLANNER)

        graph = workflow.compile(checkpointer=self.memory)
        return graph

    async def astream(
        self, conversation_id: int, message: Message
    ) -> AsyncGenerator[str, None]:
        """Stream the input to the supervisor asynchronously."""
        async for chunk in self.graph.astream(
            input={"messages": [HumanMessage(content=message.question)]},
            config={
                "configurable": {
                    "thread_id": str(conversation_id),
                },
                "callbacks": [langfuse_handler],
            },
        ):
            chunk_json = json.dumps(chunk, cls=CustomJSONEncoder)
            if "__end__" not in chunk:
                yield chunk_json
