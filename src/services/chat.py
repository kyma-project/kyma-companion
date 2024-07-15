from agents.supervisor.agent import Message, astream
from utils.logging import get_logger

logger = get_logger(__name__)


async def init_chat() -> dict:
    """ Initialize the chat """
    logger.info("Initializing chat...")
    return {"message": "Chat is initialized!"}


async def handle_request(message: Message):  # noqa: ANN201
    """ Handle a request """
    logger.info("Processing request...")

    async for chunk in astream(message):
        yield f"{chunk}\n\n".encode()
