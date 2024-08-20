from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Path
from starlette.responses import StreamingResponse

from agents.common.data import Message
from services.messages import MessagesService

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
    try:
        return StreamingResponse(
            messages_service.handle_request(conversation_id, message),
            media_type="text/event-stream",
        )
    except Exception as e:
        raise HTTPException(status_code=500) from e
