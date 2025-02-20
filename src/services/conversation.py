from collections.abc import AsyncGenerator
from typing import Protocol, cast

from langfuse.callback import CallbackHandler

from agents.common.data import Message
from agents.graph import CompanionGraph, IGraph
from agents.memory.async_redis_checkpointer import AsyncRedisSaver
from followup_questions.followup_questions import (
    FollowUpQuestionsHandler,
    IFollowUpQuestionsHandler,
)
from initial_questions.inital_questions import (
    IInitialQuestionsHandler,
    InitialQuestionsHandler,
)
from services.k8s import IK8sClient
from utils.config import Config
from utils.logging import get_logger
from utils.models.factory import IModel, IModelFactory, ModelFactory, ModelType
from utils.settings import REDIS_DB_NUMBER, REDIS_HOST, REDIS_PORT
from utils.singleton_meta import SingletonMeta

logger = get_logger(__name__)

TOKEN_LIMIT = 16_000


class IService(Protocol):
    """Service interface"""

    def new_conversation(self, k8s_client: IK8sClient, message: Message) -> list[str]:
        """Initialize a new conversation."""
        ...

    async def handle_followup_questions(self, conversation_id: str) -> list[str]:
        """Generate follow-up questions for a conversation."""
        ...

    def handle_request(
        self, conversation_id: str, message: Message, k8s_client: IK8sClient
    ) -> AsyncGenerator[bytes, None]:
        """Handle a request for a conversation"""
        ...


class ConversationService(metaclass=SingletonMeta):
    """
    Implementation of the conversation service.
    This class is a singleton and should be used to handle the conversation.
    """

    _init_questions_handler: IInitialQuestionsHandler
    _kyma_graph: IGraph
    _model_factory: IModelFactory

    def __init__(
        self,
        config: Config,
        initial_questions_handler: IInitialQuestionsHandler | None = None,
        model_factory: IModelFactory | None = None,
        followup_questions_handler: IFollowUpQuestionsHandler | None = None,
        langfuse_handler: CallbackHandler | None = None,
    ) -> None:
        try:
            self._model_factory = model_factory or ModelFactory(config=config)
            models = self._model_factory.create_models()
        except Exception:
            logger.exception("Failed to initialize models")
            raise

        model_mini = cast(IModel, models[ModelType.GPT4O_MINI])
        # Set up the initial question handler, which will handle all the logic to generate the inital questions.
        self._init_questions_handler = (
            initial_questions_handler or InitialQuestionsHandler(model=model_mini)
        )

        # Set up the followup question handler.
        self._followup_questions_handler = (
            followup_questions_handler or FollowUpQuestionsHandler(model=model_mini)
        )

        # Set up the Kyma Graph which allows access to stored conversation histories.
        checkpointer = AsyncRedisSaver.from_conn_info(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB_NUMBER
        )
        self._companion_graph = CompanionGraph(
            models, memory=checkpointer, handler=langfuse_handler
        )

    def new_conversation(self, k8s_client: IK8sClient, message: Message) -> list[str]:
        """Initialize a new conversation."""

        logger.info(
            f"Initializing conversation in namespace '{message.namespace}', "
            f"resource_type '{message.resource_kind}' and resource name {message.resource_name}"
        )

        # Fetch the context for our questions from the Kubernetes cluster.
        k8s_context = self._init_questions_handler.fetch_relevant_data_from_k8s_cluster(
            message=message, k8s_client=k8s_client
        )

        # Reduce the amount of tokens according to the limits.
        k8s_context = self._init_questions_handler.apply_token_limit(
            k8s_context, TOKEN_LIMIT
        )

        # Pass the context to the initial question handler to generate the questions.
        questions = self._init_questions_handler.generate_questions(context=k8s_context)

        return questions

    async def handle_followup_questions(self, conversation_id: str) -> list[str]:
        """Generate follow-up questions for a conversation."""

        logger.info(
            f"Generating follow-up questions for conversation: ({conversation_id})"
        )

        # Fetch the conversation history from the LangGraph.
        messages = await self._companion_graph.aget_messages(conversation_id)
        # Generate follow-up questions based on the conversation history.
        return self._followup_questions_handler.generate_questions(messages=messages)

    async def handle_request(
        self, conversation_id: str, message: Message, k8s_client: IK8sClient
    ) -> AsyncGenerator[bytes, None]:
        """Handle a request"""

        logger.info("Processing request...")

        async for chunk in self._companion_graph.astream(
            conversation_id, message, k8s_client
        ):
            yield chunk.encode()
