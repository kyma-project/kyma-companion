import json
from collections.abc import Hashable
from typing import Any, AsyncIterator, Dict, Literal, Protocol, Sequence  # noqa UP

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableSequence
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.graph.graph import CompiledGraph

from agents.common.agent import IAgent
from agents.common.constants import (
    COMMON,
    ERROR,
    EXIT,
    MESSAGES,
    NEXT,
)
from agents.common.data import Message
from agents.common.state import AgentState, Plan, SubTask, UserInput
from agents.common.utils import (
    exit_node,
    filter_messages,
)
from agents.k8s.agent import K8S_AGENT, KubernetesAgent
from agents.kyma.agent import KYMA_AGENT, KymaAgent
from agents.prompts import COMMON_QUESTION_PROMPT, FINALIZER_PROMPT, PLANNER_PROMPT
from agents.supervisor.agent import FINALIZER, SUPERVISOR, SupervisorAgent
from services.k8s import IK8sClient
from utils.langfuse import handler
from utils.logging import get_logger
from utils.models import LLM, IModel

logger = get_logger(__name__)


class CustomJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for AIMessage, HumanMessage, and SubTask.
    Default JSON cannot serialize these objects.
    """

    def default(self, obj):  # noqa D102
        if isinstance(
            obj, AIMessage | HumanMessage | SystemMessage | ToolMessage | SubTask
        ):
            return obj.__dict__
        elif isinstance(obj, IK8sClient):
            return obj.model_dump()
        return super().default(obj)


class IGraph(Protocol):
    """Graph interface."""

    def astream(
        self, conversation_id: str, message: Message, k8s_client: IK8sClient
    ) -> AsyncIterator[str]:
        """Stream the output to the caller asynchronously."""
        ...


class KymaGraph:
    """Kyma graph class. Represents all the workflow of the application."""

    models: dict[str, IModel]
    memory: BaseCheckpointSaver
    supervisor_agent: IAgent
    kyma_agent: IAgent
    k8s_agent: IAgent
    members: list[str] = []

    plan_parser = PydanticOutputParser(pydantic_object=Plan)  # type: ignore

    planner_prompt: ChatPromptTemplate

    def __init__(self, models: dict[str, IModel], memory: BaseCheckpointSaver):
        self.models = models
        self.memory = memory

        gpt_4o_mini = models[LLM.GPT4O_MINI]
        gpt_4o = models[LLM.GPT4O]

        # TODO: switch to gpt_4o when necessary
        self.kyma_agent = KymaAgent(gpt_4o_mini)

        self.k8s_agent = KubernetesAgent(gpt_4o)
        self.supervisor_agent = SupervisorAgent(
            gpt_4o, members=[KYMA_AGENT, K8S_AGENT, COMMON]
        )

        self.members = [self.kyma_agent.name, self.k8s_agent.name, COMMON]
        self._common_chain = self._create_common_chain(gpt_4o_mini)
        self.graph = self._build_graph()

    @staticmethod
    def _create_common_chain(model: IModel) -> RunnableSequence:
        """Common node chain to handle general queries."""

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", COMMON_QUESTION_PROMPT),
                MessagesPlaceholder(variable_name="messages"),
                ("human", "query: {query}"),
            ]
        )
        return prompt | model.llm  # type: ignore

    def _invoke_common_node(self, state: AgentState, subtask: str) -> str:
        """Invoke the common node."""
        return self._common_chain.invoke(  # type: ignore
            {
                "messages": filter_messages(state.messages),
                "query": subtask,
            },
        ).content

    def _common_node(self, state: AgentState) -> dict[str, Any]:
        """Common node to handle general queries."""

        for subtask in state.subtasks:
            if subtask.assigned_to == COMMON and subtask.status != "completed":
                try:
                    response = self._invoke_common_node(state, subtask.description)
                    subtask.complete()
                    return {
                        MESSAGES: [
                            AIMessage(
                                content=response,
                                name=COMMON,
                            )
                        ],
                    }
                except Exception as e:
                    logger.error(f"Error in common node: {e}")
                    return {
                        ERROR: str(e),
                        NEXT: EXIT,
                    }
        return {
            MESSAGES: [
                AIMessage(
                    content="All my subtasks are already completed.",
                    name=COMMON,
                )
            ]
        }

    def _build_graph(self) -> CompiledGraph:
        """Create a supervisor agent."""

        workflow = StateGraph(AgentState)
        workflow.add_node(SUPERVISOR, self.supervisor_agent.agent_node())
        workflow.add_node(KYMA_AGENT, self.kyma_agent.agent_node())
        workflow.add_node(K8S_AGENT, self.k8s_agent.agent_node())
        workflow.add_node(COMMON, self._common_node)
        workflow.add_node(EXIT, exit_node)

        # Define the edge: exit --> end
        workflow.add_edge(EXIT, END)
        workflow.set_entry_point(SUPERVISOR)

        # Agents should ALWAYS "report back" to the supervisor when done
        # define the edges: (KymaAgent | KubernetesAgent | Common) --> Supervisor
        for member in self.members:
            workflow.add_edge(member, SUPERVISOR)

        # The supervisor populates the "next" field in the graph state
        # which routes to a node or finishes
        conditional_map: dict[Hashable, str] = {k: k for k in self.members + [EXIT]}
        # Define the dynamic conditional edges: Supervisor --> (KymaAgent | KubernetesAgent | Common | Exit)
        workflow.add_conditional_edges(SUPERVISOR, lambda x: x.next, conditional_map)

        graph = workflow.compile(checkpointer=self.memory)
        return graph

    async def astream(
        self, conversation_id: str, message: Message, k8s_client: IK8sClient
    ) -> AsyncIterator[str]:
        """Stream the output to the caller asynchronously."""
        user_input = UserInput(**message.__dict__)
        messages = [
            SystemMessage(
                content=f"The user query is related to: {user_input.get_resource_information()}"
            ),
            HumanMessage(content=message.query),
        ]

        async for chunk in self.graph.astream(
            input={
                "messages": messages,
                "input": user_input,
                "k8s_client": k8s_client,
                "subtasks": [],
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
