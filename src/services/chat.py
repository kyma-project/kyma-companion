import asyncio
from collections.abc import AsyncGenerator

from utils.logging import get_logger
from utils.models import get_model
from utils.utils import create_ndjson_str

logger = get_logger(__name__)


async def init_chat() -> dict:
    """Initialize the chat"""
    logger.info("Initializing chat...")
    return {"message": "Chat is initialized!"}


async def handle_request() -> AsyncGenerator[str, None]:
    """Chat with the Kyma companion"""
    logger.info("Processing request...")

    llm = get_model("gpt-4o")
    logger.info(f"LLM model {llm} is created.")

    # dummy implementation
    for i in range(8):
        # return event with status
        # dummy change
        yield create_ndjson_str(
            {"step": "action", "result": "Doing Step \n" + str(i + 1)}
        )
        max_wait_count = 4
        if i < max_wait_count:
            # wait for 1 seconds
            await asyncio.sleep(1.0)

    # return final response.
    yield create_ndjson_str({"step": "output", "result": "Completed!}\n"})
