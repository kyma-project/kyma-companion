import os
from collections.abc import AsyncGenerator
from typing import Protocol

from agents.common.data import Message
from agents.graph import IGraph, KymaGraph
from agents.memory.redis_checkpointer import RedisSaver, initialize_async_pool
from utils.logging import get_logger
from utils.models import LLM, ModelFactory

logger = get_logger(__name__)

REDIS_URL = f"{os.getenv('REDIS_URL')}/0"


class IService(Protocol):
    """Service interface"""

    def init_conversation(self) -> dict:
        """Initialize the conversation"""
        ...

    """Initialize the conversation"""

    def handle_request(
        self, conversation_id: int, message: Message
    ) -> AsyncGenerator[bytes, None]:
        """Handle a request for a conversation"""
        ...


class SingletonMeta(type):
    """Singleton metaclass."""

    _instances: dict[type, object] = {}

    def __call__(cls, *args, **kwargs):  # noqa A002
        """
        Possible changes to the value of the `__init__` argument do not affect
        the returned instance.
        """
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class ConversationService(metaclass=SingletonMeta):
    """
    Implementation of the conversation service.
    This class is a singleton and should be used to handle the conversation.
    """

    kyma_graph: IGraph

    def __init__(self):
        model_factory = ModelFactory()
        model = model_factory.create_model(LLM.GPT4O_MODEL)
        memory = RedisSaver(async_connection=initialize_async_pool(url=REDIS_URL))
        self.kyma_graph = KymaGraph(model, memory)

    def init_conversation(self) -> dict:
        """Initialize the chat"""
        logger.info("Initializing chat...")
        return {"message": "Chat is initialized!"}

    async def handle_request(
        self, conversation_id: int, message: Message
    ) -> AsyncGenerator[bytes, None]:
        """Handle a request"""
        logger.info("Processing request...")
        async for chunk in self.kyma_graph.astream(conversation_id, message):
            logger.debug(f"Sending chunk: {chunk}")
            yield f"{chunk}".encode()
