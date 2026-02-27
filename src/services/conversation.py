import json
from collections.abc import AsyncGenerator
from http import HTTPStatus
from typing import Protocol, cast

from kubernetes.client import ApiException

from agents.common.constants import ERROR, ERROR_RESPONSE
from agents.common.data import Message
from agents.graph import CompanionGraph, IGraph
from agents.memory.async_redis_checkpointer import get_async_redis_saver
from followup_questions.followup_questions import (
    FollowUpQuestionsHandler,
    IFollowUpQuestionsHandler,
)
from initial_questions.inital_questions import (
    IInitialQuestionsHandler,
    InitialQuestionsHandler,
)
from services.k8s import IK8sClient
from services.usage import IUsageTracker, UsageExceedReport, UsageTracker
from utils.config import Config
from utils.logging import get_logger
from utils.models.factory import IModel, IModelFactory
from utils.models_cache import get_models
from utils.settings import (
    MAIN_MODEL_MINI_NAME,
    TOKEN_LIMIT_PER_CLUSTER,
    TOKEN_USAGE_RESET_INTERVAL,
)
from utils.singleton_meta import SingletonMeta

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

    def handle_request(self, conversation_id: str, message: Message, k8s_client: IK8sClient) -> AsyncGenerator[bytes]:
        """Handle a request for a conversation"""
        ...

    async def authorize_user(self, conversation_id: str, user_identifier: str) -> bool:
        """Authorize the user to access the conversation."""
        ...

    async def is_usage_limit_exceeded(self, cluster_id: str) -> UsageExceedReport | None:
        """Check if the token usage limit is exceeded for the given cluster_id."""
        ...


class ConversationService(metaclass=SingletonMeta):
    """
    Implementation of the conversation service.
    This class is a singleton and should be used to handle the conversation.
    """

    _init_questions_handler: IInitialQuestionsHandler
    _kyma_graph: IGraph
    _model_factory: IModelFactory | None
    _usage_limiter: IUsageTracker

    def __init__(
        self,
        config: Config,
        initial_questions_handler: IInitialQuestionsHandler | None = None,
        model_factory: IModelFactory | None = None,
        followup_questions_handler: IFollowUpQuestionsHandler | None = None,
    ) -> None:
            if model_factory is not None:
                self._model_factory = model_factory
                models = self._model_factory.create_models()
            else:
                models = get_models(config)
                self._model_factory = None  # type: ignore
        except Exception:
            logger.exception("Failed to initialize models")
            raise

        model_mini = cast(IModel, models[MAIN_MODEL_MINI_NAME])
        # Set up the initial question handler, which will handle all the logic to generate the inital questions.
        self._init_questions_handler = initial_questions_handler or InitialQuestionsHandler(model=model_mini)

        # Set up the followup question handler.
        self._followup_questions_handler = followup_questions_handler or FollowUpQuestionsHandler(model=model_mini)

        # Set up the Kyma Graph which allows access to stored conversation histories.
        checkpointer = get_async_redis_saver()
        self._usage_limiter = UsageTracker(checkpointer, TOKEN_LIMIT_PER_CLUSTER, TOKEN_USAGE_RESET_INTERVAL)

        self._companion_graph = CompanionGraph(models, memory=checkpointer)

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

        # Fetch the conversation history from the LangGraph.
        messages = await self._companion_graph.aget_messages(conversation_id)
        # Generate follow-up questions based on the conversation history.
        return self._followup_questions_handler.generate_questions(messages=messages)

    async def handle_request(
        self, conversation_id: str, message: Message, k8s_client: IK8sClient
    ) -> AsyncGenerator[bytes]:
        """Handle a request"""
        try:
            async for chunk in self._companion_graph.astream(conversation_id, message, k8s_client):
                yield chunk.encode()
        except Exception:
            logger.exception("Error during streaming")
            error_chunk = json.dumps({ERROR: {ERROR: ERROR_RESPONSE}})
            yield error_chunk.encode()

    async def authorize_user(self, conversation_id: str, user_identifier: str) -> bool:
        """Authorize the user to access the conversation."""
        owner = await self._companion_graph.aget_thread_owner(conversation_id)
        # If the owner is None, we can update the owner to the current user.
        if owner is None:
            await self._companion_graph.aupdate_thread_owner(conversation_id, user_identifier)
            return True
        # If the owner is the same as the user, we can authorize the user.
        return owner == user_identifier

    async def is_usage_limit_exceeded(self, cluster_id: str) -> UsageExceedReport | None:
        """Check if the token usage limit is exceeded for the given cluster_id."""
        # Delete expired records before checking the usage limit.
        await self._usage_limiter.adelete_expired_records(cluster_id)
        # Check if the usage limit is exceeded.
        return await self._usage_limiter.ais_usage_limit_exceeded(cluster_id)
