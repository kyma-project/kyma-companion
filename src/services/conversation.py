"""Conversation service — wires up CompanionAgent, replaces LangGraph pipeline."""

import uuid
from collections.abc import AsyncGenerator
from http import HTTPStatus
from typing import Protocol, cast

from kubernetes.client import ApiException
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langfuse.langchain import CallbackHandler

from agents.common.constants import ERROR_RESPONSE
from agents.common.data import Message
from agents.companion import CompanionAgent
from agents.tools import ToolRegistry
from followup_questions.followup_questions import (
    FollowUpQuestionsHandler,
    IFollowUpQuestionsHandler,
)
from initial_questions.inital_questions import (
    IInitialQuestionsHandler,
    InitialQuestionsHandler,
)
from rag.system import RAGSystem
from services.conversation_store import ConversationStore
from services.k8s import IK8sClient
from services.langfuse import LangfuseService, get_langfuse_metadata
from services.model_adapter import create_model_adapter
from services.response_converter import ResponseConverter
from services.usage import IUsageTracker, UsageExceedReport, UsageTracker, UsageTrackerCallback
from services.usage_store import UsageStore
from utils.config import Config
from utils.logging import get_logger
from utils.models.factory import IModel, IModelFactory, ModelFactory
from utils.settings import (
    MAIN_MODEL_MINI_NAME,
    MAIN_MODEL_NAME,
    TOKEN_LIMIT_PER_CLUSTER,
    TOKEN_USAGE_RESET_INTERVAL,
)
from utils.singleton_meta import SingletonMeta
from utils.streaming import make_error_event

logger = get_logger(__name__)

TOKEN_LIMIT = 16_000


class IService(Protocol):
    """Service interface"""

    async def new_conversation(self, k8s_client: IK8sClient, message: Message) -> list[str]:
        """Initialize a new conversation."""
        ...

    async def handle_followup_questions(self, conversation_id: str) -> list[str]:
        """Generate follow-up questions for a conversation."""
        ...

    def handle_request(
        self, conversation_id: str, message: Message, k8s_client: IK8sClient, cluster_id: str = ""
    ) -> AsyncGenerator[bytes]:
        """Handle a request for a conversation"""
        ...

    async def authorize_user(self, conversation_id: str, user_identifier: str) -> bool:
        """Authorize the user to access the conversation."""
        ...

    async def is_usage_limit_exceeded(self, cluster_id: str) -> UsageExceedReport | None:
        """Check if the token usage limit is exceeded for the given cluster_id."""
        ...


class ConversationService(metaclass=SingletonMeta):
    """Implementation of the conversation service using CompanionAgent."""

    _init_questions_handler: IInitialQuestionsHandler
    _model_factory: IModelFactory
    _usage_limiter: IUsageTracker

    def __init__(
        self,
        config: Config,
        initial_questions_handler: IInitialQuestionsHandler | None = None,
        model_factory: IModelFactory | None = None,
        followup_questions_handler: IFollowUpQuestionsHandler | None = None,
    ) -> None:
        try:
            self._model_factory = model_factory or ModelFactory(config=config)
            models = self._model_factory.create_models()
        except Exception:
            logger.exception("Failed to initialize models")
            raise

        model_mini = cast(IModel, models[MAIN_MODEL_MINI_NAME])
        self._model_main = cast(IModel, models[MAIN_MODEL_NAME])

        # Set up the initial question handler
        self._init_questions_handler = initial_questions_handler or InitialQuestionsHandler(model=model_mini)

        # Set up the followup question handler
        self._followup_questions_handler = followup_questions_handler or FollowUpQuestionsHandler(model=model_mini)

        # Set up conversation store (replaces AsyncRedisSaver for messages)
        self._conversation_store = ConversationStore()

        # Set up usage store and tracker (replaces AsyncRedisSaver for usage)
        self._usage_store = UsageStore()
        self._usage_limiter = UsageTracker(self._usage_store, TOKEN_LIMIT_PER_CLUSTER, TOKEN_USAGE_RESET_INTERVAL)

        # Set up Langfuse service
        self._langfuse = LangfuseService()

        # Set up RAG system for search_kyma_doc tool
        rag_system = None
        try:
            rag_system = RAGSystem(models)
        except Exception:
            logger.warning("Failed to initialize RAG system, search_kyma_doc will be unavailable")

        # Set up tool registry
        self._tool_registry = ToolRegistry(rag_system=rag_system)

    def _build_callbacks(self, cluster_id: str, conversation_id: str, user_id: str) -> list:
        """Build LangChain callbacks for a request (Langfuse tracing + usage tracking)."""
        callbacks = []

        # Langfuse tracing callback — one trace per conversation turn
        if self._langfuse.enabled:
            trace_id = str(uuid.uuid4())
            handler = CallbackHandler(
                trace_context={"trace_id": trace_id},
                update_trace=True,
            )
            callbacks.append(handler)

        # Usage tracking callback
        if cluster_id:
            usage_callback = UsageTrackerCallback(
                cluster_id=cluster_id,
                memory=self._usage_store,
            )
            callbacks.append(usage_callback)

        return callbacks

    def _build_langfuse_metadata(self, conversation_id: str, user_id: str) -> dict:
        """Build Langfuse metadata to pass through RunnableConfig."""
        return get_langfuse_metadata(
            user_id=user_id,
            session_id=conversation_id,
            tags=["companion-agent"],
        )

    async def new_conversation(self, k8s_client: IK8sClient, message: Message) -> list[str]:
        """Initialize a new conversation."""

        logger.info(
            f"Initializing conversation in namespace '{message.namespace}', "
            f"resource_type '{message.resource_kind}' and resource name {message.resource_name}"
        )

        # Fetch the context for our questions from the Kubernetes cluster.
        k8s_context = "No relevant context found"
        try:
            k8s_context = await self._init_questions_handler.fetch_relevant_data_from_k8s_cluster(
                message=message, k8s_client=k8s_client
            )
        except ApiException as exp:
            # if the status is 403, we just log the error and continue with an empty context.
            logger.warning(f"Error fetching data from k8s cluster: {exp}")
            if exp.status != HTTPStatus.FORBIDDEN:
                raise exp

        # Reduce the amount of tokens according to the limits.
        k8s_context = self._init_questions_handler.apply_token_limit(k8s_context, TOKEN_LIMIT)

        # Pass the context to the initial question handler to generate the questions.
        questions = self._init_questions_handler.generate_questions(context=k8s_context)

        return questions

    async def handle_followup_questions(self, conversation_id: str) -> list[str]:
        """Generate follow-up questions for a conversation."""

        logger.info(f"Generating follow-up questions for conversation: ({conversation_id})")

        # Load conversation history from new store
        history_dicts = await self._conversation_store.load_messages(conversation_id)

        # Convert to LangChain messages for the existing handler
        messages: list[BaseMessage] = []
        for msg in history_dicts:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))

        return self._followup_questions_handler.generate_questions(messages=messages)

    async def handle_request(
        self,
        conversation_id: str,
        message: Message,
        k8s_client: IK8sClient,
        cluster_id: str = "",
    ) -> AsyncGenerator[bytes]:
        """Handle a request by delegating to CompanionAgent."""
        try:
            # Build per-request callbacks for Langfuse tracing and usage tracking
            callbacks = self._build_callbacks(
                cluster_id=cluster_id,
                conversation_id=conversation_id,
                user_id=message.user_identifier or "",
            )

            # Build Langfuse metadata for RunnableConfig
            metadata = self._build_langfuse_metadata(
                conversation_id=conversation_id,
                user_id=message.user_identifier or "",
            )

            # Create per-request adapter with callbacks and metadata
            adapter = create_model_adapter(self._model_main, callbacks=callbacks, metadata=metadata)

            # Create response converter for this request
            response_converter = ResponseConverter(k8s_client)

            # Create companion agent for this request
            agent = CompanionAgent(
                adapter=adapter,
                tool_registry=self._tool_registry,
                conversation_store=self._conversation_store,
                response_converter=response_converter,
            )

            async for chunk in agent.handle_message(conversation_id, message, k8s_client):
                yield chunk
        except Exception:
            logger.exception("Error during streaming")
            yield make_error_event(ERROR_RESPONSE)

    async def authorize_user(self, conversation_id: str, user_identifier: str) -> bool:
        """Authorize the user to access the conversation."""
        owner = await self._conversation_store.get_thread_owner(conversation_id)
        # If the owner is None, we can update the owner to the current user.
        if owner is None:
            await self._conversation_store.set_thread_owner(conversation_id, user_identifier)
            return True
        # If the owner is the same as the user, we can authorize the user.
        return owner == user_identifier

    async def is_usage_limit_exceeded(self, cluster_id: str) -> UsageExceedReport | None:
        """Check if the token usage limit is exceeded for the given cluster_id."""
        # Delete expired records before checking the usage limit.
        await self._usage_limiter.adelete_expired_records(cluster_id)
        # Check if the usage limit is exceeded.
        return await self._usage_limiter.ais_usage_limit_exceeded(cluster_id)
