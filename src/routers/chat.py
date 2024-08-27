from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from starlette.responses import StreamingResponse

from agents.supervisor.agent import Message
from services.chat import Chat, ChatInterface, ConversationContext
from services.k8s import K8sClient, K8sClientInterface

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
async def conversations(ctx: ConversationContext,
                        x_cluster_url: Annotated[str, Header()],
                        x_k8s_authorization: Annotated[str, Header()],
                        x_cluster_certificate_authority_data: Annotated[str, Header()]) -> dict:
    """Endpoint to initialize a conversation with Kyma Companion and generates initial questions."""
    # initialize k8s client for the request.
    try:
        k8s_client: K8sClientInterface = K8sClient(
            api_server=x_cluster_url,
            user_token=x_k8s_authorization,
            certificate_authority_data=x_cluster_certificate_authority_data
        )
    except Exception as e:
        # TODO: add message to say that failed to connect to k8s.
        raise HTTPException(status_code=400) from e

    try:
        return await chat_service.conversations(ctx=ctx, k8s_client=k8s_client)
    except Exception as e:
        raise HTTPException(status_code=500) from e

@router.post("/")
async def chat(message: Message) -> StreamingResponse:
    """Endpoint to chat with the Kyma companion"""
    try:
        return StreamingResponse(
            chat_service.handle_request(message), media_type="text/event-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500) from e
