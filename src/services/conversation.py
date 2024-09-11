import os
import time
from collections.abc import AsyncGenerator
from typing import Protocol

from agents.common.data import Message
from agents.graph import IGraph, KymaGraph
from agents.initial_questions.inital_questions import (
    IInitialQuestionsAgent,
    InitialQuestionsAgent,
)
from agents.memory.conversation_history import ConversationMessage, QueryType
from agents.memory.redis_checkpointer import IMemory, RedisSaver, initialize_async_pool
from services.k8s import IK8sClient
from utils.logging import get_logger
from utils.models import LLM, IModel, ModelFactory
from utils.singleton_meta import SingletonMeta

logger = get_logger(__name__)

REDIS_URL = f"{os.getenv('REDIS_URL')}/0"


class IService(Protocol):
    """Service interface"""

    async def new_conversation(
        self, conversation_id: str, message: Message, k8s_client: IK8sClient
    ) -> list[str]:
        """Initialize a new conversation. Returns a list of initial questions."""
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

    kyma_graph: IGraph
    model_factory: ModelFactory
    model: IModel
    memory: IMemory
    init_questions_agent: IInitialQuestionsAgent

    def __init__(self):
        self.model_factory = ModelFactory()
        self.model = self.model_factory.create_model(LLM.GPT4O_MODEL)
        self.memory = RedisSaver(async_connection=initialize_async_pool(url=REDIS_URL))
        self.kyma_graph = KymaGraph(self.model, self.memory)
        self.init_questions_agent = InitialQuestionsAgent(model=self.model)

    async def new_conversation(
        self, conversation_id: str, message: Message, k8s_client: IK8sClient
    ) -> list[str]:
        """Initialize a new conversation."""
        logger.info(f"Initializing new conversation id: {conversation_id}.")

        # Generate initial questions for the specified resource.
        questions = await self.generate_initial_questions(
            conversation_id, message, k8s_client
        )

        # initialize the redis memory for the conversation.
        await self.memory.add_conversation_message(
            conversation_id,
            ConversationMessage(
                type=QueryType.INITIAL_QUESTIONS,
                query="",
                response="\n".join(questions),
                timestamp=time.time(),
            ),
        )

        return questions

    async def generate_initial_questions(
        self, conversation_id: str, message: Message, k8s_client: IK8sClient
    ) -> list[str]:
        """Initialize the chat"""
        logger.info(
            f"Initializing conversation ({conversation_id}) with namespace '{message.namespace}', "
            f"resource_type '{message.resource_kind}' and resource name {message.resource_name}"
        )

        # Fetch the Kubernetes context for the initial questions.
        k8s_context = self.init_questions_agent.fetch_relevant_data_from_k8s_cluster(
            message, k8s_client
        )

        # Generate questions from the context using an LLM.
        return self.init_questions_agent.generate_questions(context=k8s_context)

    async def handle_request(
        self, conversation_id: str, message: Message
    ) -> AsyncGenerator[bytes, None]:
        """Handle a request"""
        logger.info("Processing request...")
        async for chunk in self.kyma_graph.astream(conversation_id, message):
            logger.debug(f"Sending chunk: {chunk}")
            yield f"{chunk}".encode()
