from fastapi import APIRouter, HTTPException
from starlette.responses import StreamingResponse

from agents.supervisor.agent import Message
from services.chat import handle_request, init_chat

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


@router.get("/init")
async def init() -> dict:
    """ Endpoint to initialize the chat with the Kyma companion """
    return await init_chat()


@router.post("/")
async def chat(message: Message) -> StreamingResponse:
    """ Endpoint to chat with the Kyma companion """
    try:
        return StreamingResponse(
            handle_request(message),
            media_type='text/event-stream'
        )
    except Exception as e:
        raise HTTPException(status_code=500) from e
