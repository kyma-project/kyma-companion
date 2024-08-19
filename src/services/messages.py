import os
from collections.abc import AsyncIterator
from typing import Any

from agents.memory.redis_checkpointer import RedisSaver, initialize_async_pool
from agents.supervisor.agent import Message, SupervisorAgent
from utils.logging import get_logger
from utils.models import LLM, ModelFactory

logger = get_logger(__name__)


class MessagesService:
    """Chat service."""

    supervisor_agent: SupervisorAgent
    model_factory = ModelFactory()

    def __init__(self):
        model = self.model_factory.create_model(LLM.GPT4O_MODEL)
        memory = RedisSaver(
            async_connection=initialize_async_pool(url=f"{os.getenv('REDIS_URL')}/0")
        )
        self.supervisor_agent = SupervisorAgent(model, memory)

    async def init_chat(self) -> dict:
        """Initialize the chat"""
        logger.info("Initializing chat...")
        return {"message": "Chat is initialized!"}

    async def handle_request(
        self, conversation_id: int, message: Message
    ) -> AsyncIterator[Any]:
        """Handle a request"""
        logger.info("Processing request...")

        async for chunk in self.supervisor_agent.astream(conversation_id, message):
            yield f"{chunk}\n\n".encode()
