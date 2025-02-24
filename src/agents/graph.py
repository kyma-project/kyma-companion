import json
from collections.abc import AsyncIterator, Hashable
from typing import (
    Any,
    Protocol,
    cast,
)

from langchain_core.embeddings import Embeddings
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableSequence
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.graph.graph import CompiledGraph

from agents.common.agent import IAgent
from agents.common.constants import (
    COMMON,
    CONTINUE,
    MESSAGES,
    MESSAGES_SUMMARY,
    SUBTASKS,
    SUMMARIZATION,
)
from agents.common.data import Message
from agents.common.state import CompanionState, Plan, SubTask, UserInput
from agents.common.utils import should_continue
from agents.k8s.agent import K8S_AGENT, KubernetesAgent
from agents.kyma.agent import KYMA_AGENT, KymaAgent
from agents.prompts import COMMON_QUESTION_PROMPT
from agents.summarization.summarization import MessageSummarizer
from agents.supervisor.agent import SUPERVISOR, SupervisorAgent
from services.k8s import IK8sClient
from utils.chain import ainvoke_chain
from utils.logging import get_logger
from utils.models.factory import IModel, ModelType
from utils.settings import (
    SUMMARIZATION_TOKEN_LOWER_LIMIT,
    SUMMARIZATION_TOKEN_UPPER_LIMIT,
)

logger = get_logger(__name__)


class CustomJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for AIMessage, HumanMessage, and SubTask.
    Default JSON cannot serialize these objects.
    """

    def default(self, obj):  # noqa D102
        if isinstance(
            obj,
            RemoveMessage
            | AIMessage
            | HumanMessage
            | SystemMessage
            | ToolMessage
            | SubTask,
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

    async def aget_messages(self, conversation_id: str) -> list[BaseMessage]:
        """Get messages from the graph state."""
        ...


class CompanionGraph:
    """Companion graph class. Represents all the workflow of the application."""

    models: dict[str, IModel | Embeddings]
    memory: BaseCheckpointSaver
    supervisor_agent: IAgent
    kyma_agent: IAgent
    k8s_agent: IAgent
    members: list[str] = []

    plan_parser = PydanticOutputParser(pydantic_object=Plan)

    planner_prompt: ChatPromptTemplate

    def __init__(
        self,
        models: dict[str, IModel | Embeddings],
        memory: BaseCheckpointSaver,
        handler: Any = None,
    ):
        self.models = models
        self.memory = memory
        self.handler = handler

        gpt_4o_mini = models[ModelType.GPT4O_MINI]
        gpt_4o = models[ModelType.GPT4O]

        self.kyma_agent = KymaAgent(models)

        self.k8s_agent = KubernetesAgent(cast(IModel, gpt_4o))
        self.supervisor_agent = SupervisorAgent(
            models,
            members=[KYMA_AGENT, K8S_AGENT, COMMON],
        )

        self.summarization = MessageSummarizer(
            model=gpt_4o_mini,
            tokenizer_model_type=ModelType.GPT4O,
            token_lower_limit=SUMMARIZATION_TOKEN_LOWER_LIMIT,
            token_upper_limit=SUMMARIZATION_TOKEN_UPPER_LIMIT,
            messages_key=MESSAGES,
            messages_summary_key=MESSAGES_SUMMARY,
        )

        self.members = [self.kyma_agent.name, self.k8s_agent.name, COMMON]
        self._common_chain = self._create_common_chain(cast(IModel, gpt_4o_mini))
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

    async def _invoke_common_node(self, state: CompanionState, subtask: str) -> str:
        """Invoke the common node."""
        response = await ainvoke_chain(
            self._common_chain,
            {
                "messages": state.get_messages_including_summary(),
                "query": subtask,
            },
        )
        return str(response.content)

    async def _common_node(self, state: CompanionState) -> dict[str, Any]:
        """Common node to handle general queries."""

        for subtask in state.subtasks:
            if subtask.assigned_to == COMMON and subtask.status != "completed":
                try:
                    response = await self._invoke_common_node(
                        state, subtask.description
                    )
                    subtask.complete()
                    return {
                        MESSAGES: [
                            AIMessage(
                                content=response,
                                name=COMMON,
                            )
                        ],
                        SUBTASKS: state.subtasks,
                    }
                except Exception:
                    logger.exception("Error in common node")
                    return {
                        MESSAGES: [
                            AIMessage(
                                content="Sorry, I am unable to process the request.",
                                name=COMMON,
                            )
                        ],
                        SUBTASKS: state.subtasks,
                    }
        return {
            MESSAGES: [
                AIMessage(
                    content="All my subtasks are already completed.",
                    name=COMMON,
                )
            ],
            SUBTASKS: state.subtasks,
        }

    def _build_graph(self) -> CompiledGraph:
        """Create the companion parent graph."""

        # Define a new graph.
        workflow = StateGraph(CompanionState)

        # Define the nodes of the graph.
        workflow.add_node(SUPERVISOR, self.supervisor_agent.agent_node())
        workflow.add_node(KYMA_AGENT, self.kyma_agent.agent_node())
        workflow.add_node(K8S_AGENT, self.k8s_agent.agent_node())
        workflow.add_node(COMMON, self._common_node)
        workflow.add_node(SUMMARIZATION, self.summarization.summarization_node)

        # Define the edges: (KymaAgent | KubernetesAgent | Common) --> supervisor
        # The agents ALWAYS "report back" to the supervisor through summarization node.
        for member in self.members:
            workflow.add_edge(member, SUMMARIZATION)

        # Set the entrypoint: ENTRY --> summarization
        workflow.set_entry_point(SUMMARIZATION)

        # The supervisor dynamically populates the "next" field in the graph.
        conditional_map: dict[Hashable, str] = {k: k for k in self.members + [END]}
        # Define the dynamic conditional edges: supervisor --> (KymaAgent | KubernetesAgent | Common | END)
        workflow.add_conditional_edges(SUPERVISOR, lambda x: x.next, conditional_map)

        workflow.add_conditional_edges(
            SUMMARIZATION,
            should_continue,
            {
                CONTINUE: SUPERVISOR,
                END: END,
            },
        )

        # Compile the graph.
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

        x_cluster_url = k8s_client.get_api_server()
        cluster_id = x_cluster_url.split(".")[1]

        async for chunk in self.graph.astream(
            input={
                "messages": messages,
                "input": user_input,
                "k8s_client": k8s_client,
                "subtasks": [],
                "error": None,
            },
            config={
                "configurable": {
                    "thread_id": conversation_id,
                },
                "callbacks": [self.handler],
                "tags": [
                    cluster_id
                ],  # cluster_id as a tag for traceability and rate limiting
            },
        ):
            chunk_json = json.dumps(chunk, cls=CustomJSONEncoder)
            if "__end__" not in chunk:
                yield chunk_json

    async def aget_messages(self, conversation_id: str) -> list[BaseMessage]:
        """Get messages from the graph state."""
        latest_state = await self.graph.aget_state(
            {
                "configurable": {
                    "thread_id": conversation_id,
                },
            }
        )
        if latest_state.values and "messages" in latest_state.values:
            return latest_state.values["messages"]  # type: ignore
        return []
