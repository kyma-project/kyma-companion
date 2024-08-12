import os

from agents.memory.redis_checkpointer import RedisSaver, initialize_async_pool
from agents.supervisor.agent import Message, SupervisorAgent
from utils.logging import get_logger
from utils.models import create_llm

logger = get_logger(__name__)

GPT4O_MODEL = "gpt-4o"


class Chat:
    """Chat service."""

    supervisor_agent = None

    def __init__(self):
        llm = create_llm(GPT4O_MODEL)
        memory = RedisSaver(
            async_connection=initialize_async_pool(url=f"{os.getenv('REDIS_URL')}/0")
        )
        self.supervisor_agent = SupervisorAgent(llm, memory)

    async def init_chat(self) -> dict:
        """Initialize the chat"""
        logger.info("Initializing chat...")
        return {"message": "Chat is initialized!"}

    async def handle_request(self, message: Message):  # noqa: ANN201
        """Handle a request"""
        logger.info("Processing request...")

        async for chunk in self.supervisor_agent.astream(message):
            yield f"{chunk}\n\n".encode()
