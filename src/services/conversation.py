from collections.abc import AsyncGenerator
from typing import Protocol

from langchain_core.messages import HumanMessage
from langchain_redis import RedisChatMessageHistory

from agents.common.data import Message
from agents.graph import IGraph
from initial_questions.inital_questions import (
    IInitialQuestionsHandler,
)
from services.k8s import IK8sClient
from utils.logging import get_logger
from utils.settings import REDIS_URL
from utils.singleton_meta import SingletonMeta

logger = get_logger(__name__)

TOKEN_LIMIT = 16_000


class IService(Protocol):
    """Service interface"""

    def new_conversation(
        self, session_id: str, k8s_client: IK8sClient, message: Message
    ) -> list[str]:
        """Initialize a new conversation."""
        ...

    def handle_request(
        self, conversation_id: str, message: Message
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
    _redis_url: str

    def __init__(
        self,
        initial_questions_handler: IInitialQuestionsHandler,
        kyma_graph: IGraph,
        redis_url: str,
    ) -> None:
        self._init_questions_handler = initial_questions_handler
        self._kyma_graph = kyma_graph
        self._redis_url = redis_url

    def new_conversation(
        self, session_id: str, k8s_client: IK8sClient, message: Message
    ) -> list[str]:
        """Initialize a new conversation."""

        logger.info(
            f"Initializing conversation ({session_id}) with namespace '{message.namespace}', "
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

        # Store the Kubernetes context in the Redis chat history.
        history = RedisChatMessageHistory(session_id=session_id, redis_url=REDIS_URL)
        history.add_message(
            message=HumanMessage(
                content=f"These are the information I got from my Kubernetes cluster:\n{k8s_context}"
            )
        )

        return questions

    async def handle_request(
        self, conversation_id: str, message: Message
    ) -> AsyncGenerator[bytes, None]:
        """Handle a request"""

        logger.info("Processing request...")

        async for chunk in self._kyma_graph.astream(conversation_id, message):
            logger.debug(f"Sending chunk: {chunk}")
            yield chunk.encode()
