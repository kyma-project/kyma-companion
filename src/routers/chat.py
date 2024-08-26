from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import StreamingResponse

from agents.supervisor.agent import Message
from services.chat import Chat, ChatInterface, ConversationContext
from services.k8s import K8s_Access

chat_service: ChatInterface = None

def set_chat_service(chat: ChatInterface = Depends(Chat)) -> None:
    global chat_service
    chat_service = chat

set_chat_service()

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)



@router.post("/conversations")
async def conversations(ctx: ConversationContext) -> dict:
    """Endpoint to initialize a conversation with Kyma Companion and generates initial questions."""
    ### TODO: read token from header
    k8s_client = K8s_Access() ### TODO: pass K8s data
    k8s_client.listResources(api_version="v1", kind="Pod", namespace=ctx.namespace)

    # handle prompt template

    return await chat_service.conversations(ctx=ctx)


@router.post("/")
async def chat(message: Message) -> StreamingResponse:
    """Endpoint to chat with the Kyma companion"""
    try:
        return StreamingResponse(
            chat_service.handle_request(message), media_type="text/event-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500) from e
