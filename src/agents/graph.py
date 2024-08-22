import json
from collections.abc import Hashable, Sequence
from typing import Any, AsyncIterator, Dict, Literal, Protocol  # noqa UP

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.constants import END, START
from langgraph.graph import MessagesState, StateGraph
from langgraph.graph.graph import CompiledGraph

from agents.common.data import Message
from agents.common.state import AgentState, Plan, SubTask
from agents.k8s.agent import K8S_AGENT, KubernetesAgent
from agents.kyma.agent import KYMA_AGENT, KymaAgent
from agents.supervisor.agent import SUPERVISOR, SupervisorAgent
from utils.langfuse import handler
from utils.logging import get_logger
from utils.models import Model

logger = get_logger(__name__)

PLANNER = "Planner"
FINALIZER = "Finalize"


def should_continue(state: MessagesState) -> Literal["action", "__end__"]:
    """Return the next node to execute."""
    last_message = state["messages"][-1]
    return "action" if last_message.tool_calls else "__end__"


def filter_messages(
    messages: Sequence[BaseMessage], last_messages_number: int = 10
) -> Sequence[BaseMessage]:
    """This is very simple helper function which only ever uses the last four messages"""
    return messages[-last_messages_number:]


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder."""

    def default(self, obj):  # noqa D102
        if isinstance(obj, AIMessage | HumanMessage | SubTask):
            return obj.__dict__
        return super().default(obj)


class Graph(Protocol):
    """Graph interface."""

    def astream(self, conversation_id: int, message: Message) -> AsyncIterator[str]:
        """Stream the output to the caller asynchronously."""
        ...


class KymaGraph:
    """Kyma graph class. Represents all the workflow of the application."""

    model: Model
    memory: BaseCheckpointSaver
    supervisor_agent: SupervisorAgent
    kyma_agent: KymaAgent
    k8s_agent: KubernetesAgent
    members: list[str] = []

    parser = PydanticOutputParser(pydantic_object=Plan)

    def __init__(self, model: Model, memory: BaseCheckpointSaver):
        self.model = model
        self.memory = memory

        self.kyma_agent = KymaAgent(model)
        self.k8s_agent = KubernetesAgent(model)
        self.supervisor_agent = SupervisorAgent(model)

        self.members = [self.kyma_agent.name, self.k8s_agent.name]
        self.graph = self._build_graph()

    def _plan(self, state: AgentState) -> dict[str, Any]:
        """Breaks down the given user query into sub-tasks."""

        state.messages = filter_messages(state.messages)

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
                config={"callbacks": [handler]},
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
            config={"callbacks": [handler]},
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

    def _build_graph(self) -> CompiledGraph:
        """Create a supervisor agent."""

        workflow = StateGraph(AgentState)
        workflow.add_node(FINALIZER, self.generate_final_response)
        workflow.add_node(KYMA_AGENT, self.kyma_agent.agent_node)
        workflow.add_node(K8S_AGENT, self.k8s_agent.agent_node)
        workflow.add_node(SUPERVISOR, self.supervisor_agent.agent_node)
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
    ) -> AsyncIterator[str]:
        """Stream the output to the caller asynchronously."""
        async for chunk in self.graph.astream(
            input={"messages": [HumanMessage(content=message.query)]},
            config={
                "configurable": {
                    "thread_id": str(conversation_id),
                },
                "callbacks": [handler],
            },
        ):
            chunk_json = json.dumps(chunk, cls=CustomJSONEncoder)
            if "__end__" not in chunk:
                yield chunk_json
