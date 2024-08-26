import os
from abc import ABC, abstractmethod

from pydantic import BaseModel, field_validator

from agents.memory.redis_checkpointer import RedisSaver, initialize_async_pool
from agents.supervisor.agent import Message, SupervisorAgent
from utils.logging import get_logger
from utils.models import create_llm

logger = get_logger(__name__)

GPT4O_MODEL = "gpt-4o"

class ConversationContext(BaseModel):
    resource_type: str
    resource_name: str = ""
    namespace: str = "default"

    @field_validator("resource_type")
    def _check_not_empty(cls, value: str) -> str:
        if not value.strip(): # Check if the string is empty or only contains whitespace.
            raise ValueError("resource_type cannot be empty")
        return value

class ChatInterface(ABC):
    """Interface for Chat service."""
    @abstractmethod
    async def conversations(self, ctx: ConversationContext) -> dict:
        """Initialize the chat"""

    @abstractmethod
    async def handle_request(self, message: Message):
        """Handle a request"""


class Chat(ChatInterface):
    """Chat service."""

    supervisor_agent = None

    def __init__(self):
        llm = create_llm(GPT4O_MODEL)
        memory = RedisSaver(
            async_connection=initialize_async_pool(url=f"{os.getenv('REDIS_URL')}/0")
        )
        self.supervisor_agent = SupervisorAgent(llm, memory)

    async def conversations(self, ctx: ConversationContext) -> dict:
        """Initialize the chat"""
        logger.info(f"Initializing chat with namespace '{ctx.namespace}', resource_type '{ctx.resource_type}' and resource name {ctx.resource_name}")
        ### TODO: How do we handle the K8S token?
        

        return {"message": "Chat is initialized!"}

    async def handle_request(self, message: Message):  # noqa: ANN201
        """Handle a request"""
        logger.info("Processing request...")

        async for chunk in self.supervisor_agent.astream(message):
            yield f"{chunk}\n\n".encode()