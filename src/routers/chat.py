from fastapi import APIRouter
from starlette.responses import StreamingResponse

from services.chat import handle_request, init_chat

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


@router.get("/init")
async def init() -> dict:
    """Endpoint to initialize the chat with the Kyma companion"""
    return await init_chat()


@router.get("/")
async def chat() -> StreamingResponse:
    """Endpoint to chat with the Kyma companion"""
    return StreamingResponse(handle_request(), media_type="text/event-stream")
