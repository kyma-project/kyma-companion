import json
from collections.abc import Hashable
from typing import Any, AsyncIterator, Dict, Literal, Protocol  # noqa UP

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.graph.graph import CompiledGraph

from agents.common.agent import IAgent
from agents.common.constants import COMMON, EXIT, PLANNER
from agents.common.data import Message
from agents.common.state import AgentState, Plan, SubTask, UserInput
from agents.common.utils import exit_node, should_exit
from agents.k8s.agent import K8S_AGENT, KubernetesAgent
from agents.kyma.agent import KYMA_AGENT, KymaAgent
from agents.prompts import COMMON_QUESTION_PROMPT, FINALIZER_PROMPT, PLANNER_PROMPT
from agents.supervisor.agent import FINALIZER, SUPERVISOR, SupervisorAgent
from utils.langfuse import handler
from utils.logging import get_logger
from utils.models import IModel

logger = get_logger(__name__)


class CustomJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for AIMessage, HumanMessage, and SubTask.
    Default JSON cannot serialize these objects.
    """

    def default(self, obj):  # noqa D102
        if isinstance(obj, AIMessage | HumanMessage | SubTask):
            return obj.__dict__
        return super().default(obj)


class IGraph(Protocol):
    """Graph interface."""

    def astream(self, conversation_id: str, message: Message) -> AsyncIterator[str]:
        """Stream the output to the caller asynchronously."""
        ...


class KymaGraph:
    """Kyma graph class. Represents all the workflow of the application."""

    model: IModel
    memory: BaseCheckpointSaver
    supervisor_agent: IAgent
    kyma_agent: IAgent
    k8s_agent: IAgent
    members: list[str] = []

    parser = PydanticOutputParser(pydantic_object=Plan)  # type: ignore

    def __init__(self, model: IModel, memory: BaseCheckpointSaver):
        self.model = model
        self.memory = memory

        self.kyma_agent = KymaAgent(model)
        self.k8s_agent = KubernetesAgent(model)
        self.supervisor_agent = SupervisorAgent(
            model, members=[KYMA_AGENT, K8S_AGENT, COMMON]
        )

        self.members = [self.kyma_agent.name, self.k8s_agent.name, COMMON]
        self.graph = self._build_graph()

    def _plan(self, state: AgentState) -> dict[str, Any]:
        """Breaks down the given user query into sub-tasks."""

        planner_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", PLANNER_PROMPT),
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
                "error": None,
            }
        except Exception as e:
            logger.error(f"Error in planning: {e}")
            return {
                "error": str(e),
                "messages": [
                    AIMessage(
                        content=f"Error in planning: {e}",
                        name=PLANNER,
                    )
                ],
            }

    def common_node(self, state: AgentState) -> dict[str, Any]:
        """Common node to handle general queries."""

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", COMMON_QUESTION_PROMPT),
                MessagesPlaceholder(variable_name="messages"),
                ("human", "query: {query}"),
            ]
        )
        chain = prompt | self.model.llm

        for subtask in state.subtasks:
            if subtask.assigned_to == COMMON and subtask.status != "completed":
                try:
                    response = chain.invoke(
                        {
                            "messages": state.messages,
                            "query": subtask.description,
                        },
                        config={"callbacks": [handler]},
                    ).content
                    subtask.complete()
                    return {
                        "messages": [
                            AIMessage(
                                content=response,
                                name=COMMON,
                            )
                        ],
                    }
                except Exception as e:
                    logger.error(f"Error in common node: {e}")
                    return {
                        "error": str(e),
                        "messages": [
                            AIMessage(
                                content=f"Error occurred: {e}",
                                name=COMMON,
                            )
                        ],
                    }
        return {
            "messages": [
                AIMessage(
                    content="All my subtasks are already completed.",
                    name=COMMON,
                )
            ]
        }

    def generate_final_response(self, state: AgentState) -> dict[str, Any]:
        """Generate the final response."""

        prompt = ChatPromptTemplate.from_messages(
            [
                MessagesPlaceholder(variable_name="messages"),
                ("system", FINALIZER_PROMPT),
            ]
        ).partial(members=", ".join(self.members), query=state.input.query)
        final_response_chain = prompt | self.model.llm
        state.final_response = final_response_chain.invoke(
            {"messages": state.messages},
            config={"callbacks": [handler]},
        ).content

        return {
            "final_response": state.final_response,
            "messages": [
                AIMessage(
                    content=state.final_response if state.final_response else "",
                    name=FINALIZER,
                )
            ],
            "next": END,
        }

    def _build_graph(self) -> CompiledGraph:
        """Create a supervisor agent."""

        workflow = StateGraph(AgentState)
        workflow.add_node(FINALIZER, self.generate_final_response)
        workflow.add_node(KYMA_AGENT, self.kyma_agent.agent_node())
        workflow.add_node(K8S_AGENT, self.k8s_agent.agent_node())
        workflow.add_node(COMMON, self.common_node)

        workflow.add_node(SUPERVISOR, self.supervisor_agent.agent_node())
        workflow.add_node(PLANNER, self._plan)
        workflow.add_node(EXIT, exit_node)

        # routing to the exit node in case of an error
        workflow.add_conditional_edges(
            PLANNER, should_exit, {"exit": EXIT, "continue": SUPERVISOR}
        )
        workflow.add_edge(EXIT, END)

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
        self, conversation_id: str, message: Message
    ) -> AsyncIterator[str]:
        """Stream the output to the caller asynchronously."""
        async for chunk in self.graph.astream(
            input={
                "messages": [HumanMessage(content=message.query)],
                "input": UserInput(**message.dict()),
            },
            config={
                "configurable": {
                    "thread_id": conversation_id,
                },
                "callbacks": [handler],
            },
        ):
            chunk_json = json.dumps(chunk, cls=CustomJSONEncoder)
            if "__end__" not in chunk:
                yield chunk_json
