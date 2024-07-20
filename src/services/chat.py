import os

from agents.memory.redis_checkpointer import RedisSaver, initialize_async_pool
from agents.supervisor.agent import Message, SupervisorAgent
from utils.logging import get_logger
from utils.models import create_llm

logger = get_logger(__name__)

llm = create_llm("gpt-4o")

checkpointer = RedisSaver(async_connection=initialize_async_pool(url=f"{os.getenv('REDIS_URL')}/0"))

supervisor_agent = SupervisorAgent(llm, checkpointer)


async def init_chat() -> dict:
    """ Initialize the chat """
    logger.info("Initializing chat...")
    return {"message": "Chat is initialized!"}


async def handle_request(message: Message):  # noqa: ANN201
    """ Handle a request """
    logger.info("Processing request...")

    async for chunk in supervisor_agent.astream(message):
        yield f"{chunk}\n\n".encode()
