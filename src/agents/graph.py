import json
from collections.abc import AsyncIterator
from typing import Any, Protocol, cast

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.embeddings import Embeddings
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig, RunnableSequence
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.constants import END
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

from agents.common.constants import (
    GATEKEEPER,
    MESSAGES,
    NEXT,
    RESPONSE_HELLO,
    RESPONSE_QUERY_OUTSIDE_DOMAIN,
    RESPONSE_UNABLE_TO_PROCESS,
    UNKNOWN,
)
from agents.common.data import Message
from agents.common.state import (
    CompanionState,
    GatekeeperResponse,
    GraphInput,
    UserInput,
)
from agents.common.utils import filter_valid_messages, get_resource_context_message
from agents.kyma.agent import KYMA_AGENT, KymaAgent
from agents.memory.async_redis_checkpointer import IUsageMemory
from agents.prompts import GATEKEEPER_INSTRUCTIONS, GATEKEEPER_PROMPT
from services.k8s import IK8sClient
from services.langfuse import LangfuseService, get_langfuse_metadata
from services.usage import UsageTrackerCallback
from utils.chain import ainvoke_chain
from utils.logging import get_logger
from utils.models.factory import IModel
from utils.settings import MAIN_MODEL_NAME

logger = get_logger(__name__)


class CustomJSONEncoder(json.JSONEncoder):
    """
    Custom JSON encoder for AIMessage, HumanMessage, etc.
    Default JSON cannot serialize these objects.
    """

    def default(self, o):  # noqa D102
        """Custom JSON encoder for RemoveMessage, AIMessage, HumanMessage, SystemMessage, ToolMessage."""
        if isinstance(
            o,
            RemoveMessage | AIMessage | HumanMessage | SystemMessage | ToolMessage,
        ):
            return o.__dict__
        elif isinstance(o, IK8sClient):
            return o.model_dump()
        elif hasattr(o, "model_dump_json"):
            return o.model_dump_json()
        elif hasattr(o, "model_dump"):
            return o.model_dump()
        return super().default(o)


class IGraph(Protocol):
    """Graph interface."""

    def astream(self, conversation_id: str, message: Message, k8s_client: IK8sClient) -> AsyncIterator[str]:
        """Stream the output to the caller asynchronously."""
        ...

    async def aget_messages(self, conversation_id: str) -> list[BaseMessage]:
        """Get messages from the graph state."""
        ...


class CompanionGraph:
    """Companion graph class. Represents all the workflow of the application."""

    models: dict[str, IModel | Embeddings]
    memory: BaseCheckpointSaver
    kyma_agent: KymaAgent

    def __init__(
        self,
        models: dict[str, IModel | Embeddings],
        memory: BaseCheckpointSaver,
    ):
        self.models = models
        self.memory = memory

        main_model = models[MAIN_MODEL_NAME]

        self.kyma_agent = KymaAgent(models)
        self._gatekeeper_chain = self._create_gatekeeper_chain(cast(IModel, main_model))
        self.graph = self._build_graph()

    @staticmethod
    def _create_gatekeeper_chain(model: IModel) -> RunnableSequence:
        """Gatekeeper node chain to handle general queries
        and queries that can answered from conversation history."""

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", GATEKEEPER_PROMPT),
                MessagesPlaceholder(variable_name="messages"),
                ("system", GATEKEEPER_INSTRUCTIONS),
            ]
        )
        return prompt | model.llm.with_structured_output(GatekeeperResponse, method="function_calling")  # type: ignore

    async def _invoke_gatekeeper_node(self, state: CompanionState) -> GatekeeperResponse:
        """Invoke the Gatekeeper node."""
        response: Any = await ainvoke_chain(
            self._gatekeeper_chain,
            {
                "messages": filter_valid_messages(state.get_messages_including_summary()),
            },
        )

        gatekeeper_response = cast(GatekeeperResponse, response)
        gatekeeper_response.forward_query = False

        if gatekeeper_response.is_prompt_injection or gatekeeper_response.is_security_threat:
            logger.debug("Prompt injection or security issue detected")
            gatekeeper_response.direct_response = RESPONSE_QUERY_OUTSIDE_DOMAIN
        elif gatekeeper_response.category == "Greeting":
            logger.debug("Gatekeeper responding to greeting")
            gatekeeper_response.direct_response = RESPONSE_HELLO
        elif gatekeeper_response.category in ["About You"] and gatekeeper_response.direct_response:
            logger.debug("Gatekeeper responding with direct response for about you category")
        elif gatekeeper_response.category in ["Kyma", "Kubernetes", "Programming"]:
            logger.debug("Gatekeeper forwarding the query")
            gatekeeper_response.forward_query = True
        else:
            logger.debug("Gatekeeper responding with default response because no category matched")
            gatekeeper_response.direct_response = RESPONSE_QUERY_OUTSIDE_DOMAIN

        return gatekeeper_response

    async def _gatekeeper_node(self, state: CompanionState) -> dict[str, Any]:
        """Gatekeeper node to handle general and queries that can answered from conversation history."""

        try:
            gatekeeper_response = await self._invoke_gatekeeper_node(state)
            if gatekeeper_response.forward_query:
                logger.debug("Gatekeeper node forwarding the query to Kyma agent")
                return {
                    NEXT: KYMA_AGENT,
                }

            logger.debug("Gatekeeper node directly responding")
            return {
                NEXT: END,
                MESSAGES: [
                    AIMessage(
                        content=(
                            gatekeeper_response.direct_response
                            if gatekeeper_response.direct_response
                            else RESPONSE_UNABLE_TO_PROCESS
                        ),
                        name=GATEKEEPER,
                    )
                ],
            }
        except Exception:
            logger.exception("Error in gatekeeper node")
            return {
                NEXT: END,
                MESSAGES: [
                    AIMessage(
                        content="Sorry, I am unable to process the request.",
                        name=GATEKEEPER,
                    )
                ],
            }

    def _build_graph(self) -> CompiledStateGraph:
        """Create the companion parent graph."""

        workflow = StateGraph(CompanionState)

        workflow.add_node(GATEKEEPER, self._gatekeeper_node)
        workflow.add_node(KYMA_AGENT, self.kyma_agent.agent_node())

        workflow.set_entry_point(GATEKEEPER)

        workflow.add_conditional_edges(
            GATEKEEPER,
            lambda x: x.next,
            {
                KYMA_AGENT: KYMA_AGENT,
                END: END,
            },
        )

        workflow.add_edge(KYMA_AGENT, END)

        return workflow.compile(checkpointer=self.memory)

    async def astream(self, conversation_id: str, message: Message, k8s_client: IK8sClient) -> AsyncIterator[str]:
        """Stream the output to the caller asynchronously."""
        user_input = UserInput(**message.__dict__)
        messages: list[BaseMessage] = [HumanMessage(content=message.query)]
        resource_context_message = get_resource_context_message(user_input)
        if resource_context_message:
            messages.insert(
                0,
                resource_context_message,
            )

        x_cluster_url = k8s_client.get_api_server()
        cluster_id = x_cluster_url.split(".")[1]

        graph_input = GraphInput(
            messages=messages,
            input=user_input,
            k8s_client=k8s_client,
            error=None,
        )

        callbacks: list[BaseCallbackHandler] = [
            UsageTrackerCallback(cluster_id, cast(IUsageMemory, self.memory)),
        ]

        try:
            langfuse_handler = LangfuseService().get_callback_handler()
            if langfuse_handler:
                callbacks.append(langfuse_handler)
        except Exception:
            logger.warning("Failed to get Langfuse callback handler. Skipping Langfuse trace...", exc_info=True)

        run_config = RunnableConfig(
            configurable={
                "thread_id": conversation_id,
            },
            callbacks=callbacks,
            tags=[cluster_id],
            metadata=get_langfuse_metadata(
                message.user_identifier or UNKNOWN,
                cluster_id,
                [cluster_id],
            ),
        )

        async for chunk in self.graph.astream(input=graph_input, config=run_config):
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

    async def aget_thread_owner(self, conversation_id: str) -> str | None:
        """Get the owner of the thread."""
        state = await self.graph.aget_state(
            {
                "configurable": {
                    "thread_id": conversation_id,
                },
            }
        )
        if state and state.values and "thread_owner" in state.values and state.values["thread_owner"] != "":
            return str(state.values["thread_owner"])
        return None

    async def aupdate_thread_owner(self, conversation_id: str, user_identifier: str) -> None:
        """Update the owner of the thread."""
        await self.graph.aupdate_state(
            {
                "configurable": {
                    "thread_id": conversation_id,
                },
            },
            {
                "thread_owner": user_identifier,
            },
        )
