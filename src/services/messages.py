import os
from collections.abc import AsyncIterator
from typing import AsyncGenerator

from agents.common.data import Message
from agents.graph import Graph, KymaGraph
from agents.memory.redis_checkpointer import RedisSaver, initialize_async_pool
from utils.logging import get_logger
from utils.models import LLM, ModelFactory

logger = get_logger(__name__)


class MessagesService:
    """Chat service."""

    kyma_graph: Graph

    def __init__(self):
        model_factory = ModelFactory()
        model = model_factory.create_model(LLM.GPT4O_MODEL)
        memory = RedisSaver(
            async_connection=initialize_async_pool(url=f"{os.getenv('REDIS_URL')}/0")
        )
        self.kyma_graph = KymaGraph(model, memory)

    async def init_chat(self) -> dict:
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
            yield f"{chunk}\n\n".encode()
