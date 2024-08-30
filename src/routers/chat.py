from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from starlette.responses import StreamingResponse
from fastapi.responses import JSONResponse

from agents.supervisor.agent import Message
from services.chat import Chat, ChatInterface, ConversationContext
from services.k8s import K8sClient, K8sClientInterface
from utils.utils import create_session_id
from routers.common import InitialQuestionsResponse, SESSION_ID_HEADER
from utils.logging import get_logger

logger = get_logger(__name__)
chat_service: ChatInterface = Chat()


router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)


@router.post("/conversations", response_model=InitialQuestionsResponse)
async def conversations(ctx: ConversationContext,
                        x_cluster_url: Annotated[str, Header()],
                        x_k8s_authorization: Annotated[str, Header()],
                        x_cluster_certificate_authority_data: Annotated[str, Header()],
                        session_id: Annotated[str, Header()] = "") -> dict:
    """Endpoint to initialize a conversation with Kyma Companion and generates initial questions."""
    logger.info(f"Initializing new conversation.")

    # initialize with the session_id.
    if session_id != "":
        ctx.conversation_id = session_id
    else:
        ctx.conversation_id = create_session_id()

    # initialize k8s client for the request.    
    try:
        k8s_client: K8sClientInterface = K8sClient(
            api_server=x_cluster_url,
            user_token=x_k8s_authorization,
            certificate_authority_data=x_cluster_certificate_authority_data
        )
    except Exception as e:
        # TODO: add message to say that failed to connect to k8s.
        logger.error(e)
        raise HTTPException(status_code=400) from e

    try:
        questions = await chat_service.new_conversation(ctx=ctx, k8s_client=k8s_client)
        response = InitialQuestionsResponse(initial_questions=questions, conversation_id=ctx.conversation_id)
        # return response with session_id in the header.
        return JSONResponse(content=response, headers={SESSION_ID_HEADER: ctx.conversation_id})
    except Exception as e:
        logger.error(e)
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
