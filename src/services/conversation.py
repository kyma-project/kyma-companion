from collections.abc import AsyncGenerator
from typing import Protocol

from langchain_core.messages import HumanMessage
from langchain_redis import RedisChatMessageHistory

from agents.common.data import Message
from agents.graph import CompanionGraph, IGraph
from agents.memory.redis_checkpointer import RedisSaver, initialize_async_pool
from followup_questions.followup_questions import (
    FollowUpQuestionsHandler,
    IFollowUpQuestionsHandler,
)
from initial_questions.inital_questions import (
    IInitialQuestionsHandler,
    InitialQuestionsHandler,
)
from services.k8s import IK8sClient
from utils.logging import get_logger
from utils.models import LLM, IModel, ModelFactory
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

    _model: IModel
    _model_mini: IModel
    _init_questions_handler: IInitialQuestionsHandler
    _companion_graph: IGraph

    def __init__(
        self,
        initial_questions_handler: IInitialQuestionsHandler | None = None,
        followup_questions_handler: IFollowUpQuestionsHandler | None = None,
    ) -> None:
        # Set up the Model, which contains the llm.
        self._model_mini = ModelFactory().create_model(LLM.GPT4O_MINI)

        # Set up the initial question handler, which will handle all the logic to generate the inital questions.
        self._init_questions_handler = (
            initial_questions_handler or InitialQuestionsHandler(model=self._model_mini)
        )

        # Set up the followup question handler.
        self._followup_questions_handler = (
            followup_questions_handler
            or FollowUpQuestionsHandler(model=self._model_mini)
        )

        self._model = ModelFactory().create_model(LLM.GPT4O)
        # Set up the Companion Graph which allows access to stored conversation histories.
        redis_saver = RedisSaver(async_connection=initialize_async_pool(url=REDIS_URL))
        self._companion_graph = CompanionGraph(
            models={LLM.GPT4O: self._model, LLM.GPT4O_MINI: self._model_mini},
            memory=redis_saver,
        )

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
            logger.debug(f"Sending chunk: {chunk}")
            yield chunk.encode()
