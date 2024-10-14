import json
from typing import Any, AsyncIterator, Dict, Literal, Protocol  # noqa UP


from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableSequence
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import StateGraph
from langgraph.graph.graph import CompiledGraph

from agents.common.utils import CustomJSONEncoder
from agents.common.agent import IAgent
from agents.common.constants import (
    COMMON,
    CONTINUE,
    ERROR,
    EXIT,
    MESSAGES,
    NEXT,
    PLANNER,
    SUPERVISOR,
)
from agents.common.data import Message
from agents.common.state import AgentState, UserInput
from agents.common.utils import (
    exit_node,
    filter_messages,
    next_step,
)
from agents.k8s.agent import K8S_AGENT, KubernetesAgent
from agents.kyma.agent import KYMA_AGENT, KymaAgent
from agents.prompts import COMMON_QUESTION_PROMPT
from agents.supervisor.agent import SupervisorAgent
from services.k8s import IK8sClient
from utils.langfuse import handler
from utils.logging import get_logger
from utils.models import IModel

logger = get_logger(__name__)


class IGraph(Protocol):
    """Graph interface."""

    def astream(
        self, conversation_id: str, message: Message, k8s_client: IK8sClient
    ) -> AsyncIterator[str]:
        """Stream the output to the caller asynchronously."""
        ...


class KymaGraph:
    """Kyma graph class. Represents all the workflow of the application."""

    model: IModel
    memory: BaseCheckpointSaver
    supervisor_agent: IAgent
    kyma_agent: IAgent
    k8s_agent: IAgent

    def __init__(self, model: IModel, memory: BaseCheckpointSaver):
        self.model = model
        self.memory = memory
        self.kyma_agent = KymaAgent(model)
        self.k8s_agent = KubernetesAgent(model)
        self.supervisor_agent = SupervisorAgent(
            model, members=[KYMA_AGENT, K8S_AGENT, COMMON]
        )
        self.graph = self._build_graph()

    def _common_node_chain(self) -> RunnableSequence:
        """Common node chain to handle general queries."""

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", COMMON_QUESTION_PROMPT),
                MessagesPlaceholder(variable_name="messages"),
                ("human", "query: {query}"),
            ]
        )
        return prompt | self.model.llm  # type: ignore

    def common_node(self, state: AgentState) -> dict[str, Any]:
        """Common node to handle general queries."""

        chain = self._common_node_chain()

        for subtask in state.subtasks:
            if subtask.assigned_to == COMMON and subtask.status != "completed":
                try:
                    response = chain.invoke(
                        {
                            "messages": filter_messages(state.messages),
                            "query": subtask.description,
                        },
                    ).content
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
        workflow.add_node(KYMA_AGENT, self.kyma_agent.agent_node())
        workflow.add_node(K8S_AGENT, self.k8s_agent.agent_node())
        workflow.add_node(COMMON, self.common_node)

        workflow.add_node(SUPERVISOR, self.supervisor_agent.agent_node())
        workflow.add_node(EXIT, exit_node)

        # routing to the exit node in case of an error
        workflow.add_conditional_edges(
            PLANNER,
            next_step,
            {EXIT: EXIT, CONTINUE: SUPERVISOR},
        )

        graph = workflow.compile(checkpointer=self.memory)
        return graph

    async def astream(
        self, conversation_id: str, message: Message, k8s_client: IK8sClient
    ) -> AsyncIterator[str]:
        """Stream the output to the caller asynchronously."""
        user_input = UserInput(**message.dict())
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
