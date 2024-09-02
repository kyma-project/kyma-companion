import json
from collections.abc import AsyncGenerator
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Path
from starlette.responses import StreamingResponse

from agents.common.data import Message
from services.conversation import ConversationService, IService
from utils.logging import get_logger

logger = get_logger(__name__)


def get_conversation_service() -> IService:
    """Dependency to get the conversation service instance"""
    return ConversationService()


router = APIRouter(
    prefix="/conversations",
    tags=["conversations"],
)


@router.get("/init")
async def init() -> dict:
    """Endpoint to initialize the chat with the Kyma companion"""
    return {"message": "Chat is initialized!"}


@router.post("/{conversation_id}/messages")
async def messages(
    conversation_id: Annotated[
        int, Path(title="The ID of the conversation to continue")
    ],
    message: Annotated[Message, Body(title="The message to send")],
    service: IService = Depends(get_conversation_service),  # noqa B008
) -> StreamingResponse:
    """Endpoint to send a message to the Kyma companion"""

    async def error_handling_generator() -> AsyncGenerator[bytes, None]:
        try:
            async for chunk in service.handle_request(conversation_id, message):
                json_chunk = json.dumps({"status": 200, "data": f"{chunk.decode()}"})
                yield f"{json_chunk}\n".encode()
        except Exception as e:
            logger.exception(f"An error occurred: {str(e)}")
            json_chunk = json.dumps(
                {"status": HTTPStatus.INTERNAL_SERVER_ERROR, "message": f"Error: {e}"}
            )
            yield f"{json_chunk}\n".encode()

    return StreamingResponse(
        error_handling_generator(),
        media_type="text/event-stream",
    )
