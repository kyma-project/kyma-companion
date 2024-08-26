import json
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Body, Path
from starlette.responses import StreamingResponse

from agents.common.data import Message
from services.messages import MessagesService
from utils.logging import get_logger

logger = get_logger(__name__)

messages_service = MessagesService()
router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
)


@router.get("/init")
async def init() -> dict:
    """Endpoint to initialize the chat with the Kyma companion"""
    return await messages_service.init_chat()


@router.post("/{conversation_id}/messages")
async def messages(
    conversation_id: Annotated[
        int, Path(title="The ID of the conversation to continue")
    ],
    message: Annotated[Message, Body(title="The message to send")],
) -> StreamingResponse:
    """Endpoint to send a message to the Kyma companion"""

    async def error_handling_generator() -> AsyncGenerator[bytes, None]:
        try:
            async for chunk in messages_service.handle_request(
                conversation_id, message
            ):
                json_chunk = json.dumps({"status": 200, "data": f"{chunk.decode()}"})
                yield f"{json_chunk}\n".encode()
        except Exception as e:
            logger.exception(f"An error occurred: {str(e)}")
            json_chunk = json.dumps({"status": 500, "message": f"Error: {e}"})
            yield f"{json_chunk}\n".encode()

    return StreamingResponse(
        error_handling_generator(),
        media_type="text/event-stream",
    )
