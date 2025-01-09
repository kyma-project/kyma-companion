from datetime import datetime, UTC
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Path
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse, StreamingResponse

from agents.common.data import Message
from agents.common.utils import get_current_day_timestamps_utc, hash_url
from routers.common import (
    API_PREFIX,
    SESSION_ID_HEADER,
    FollowUpQuestionsResponse,
    InitConversationBody,
    InitialQuestionsResponse,
)
from services.conversation import ConversationService, IService
from services.k8s import IK8sClient, K8sClient
from utils.langfuse import LangfuseAPI
from utils.logging import get_logger
from utils.response import prepare_chunk_response
from utils.settings import TOKEN_LIMIT_PER_CLUSTER
from utils.utils import create_session_id

logger = get_logger(__name__)


def get_conversation_service() -> IService:
    """Dependency to get the conversation service instance"""
    return ConversationService()


router = APIRouter(
    prefix=f"{API_PREFIX}/conversations",
    tags=["conversations"],
)


@router.post("/", response_model=InitialQuestionsResponse)
async def init_conversation(
    data: InitConversationBody,
    x_cluster_url: Annotated[str, Header()],
    x_k8s_authorization: Annotated[str, Header()],
    x_cluster_certificate_authority_data: Annotated[str, Header()],
    session_id: Annotated[str, Header()] = "",
    service: IService = Depends(get_conversation_service),  # noqa B008
) -> JSONResponse:
    """Endpoint to initialize a conversation with Kyma Companion and generates initial questions."""

    logger.info("Initializing new conversation.")



    # Initialize with the session_id. Create a new session_id if not provided.
    session_id = session_id if session_id else create_session_id()

    # Initialize k8s client for the request.
    try:
        k8s_client: IK8sClient = K8sClient(
            api_server=x_cluster_url,
            user_token=x_k8s_authorization,
            certificate_authority_data=x_cluster_certificate_authority_data,
        )
    except Exception as e:
        logger.error(e)
        raise HTTPException(
            status_code=400, detail=f"failed to connect to the cluster: {str(e)}"
        ) from e

    try:
        # Create initial questions.
        questions = service.new_conversation(
            k8s_client=k8s_client,
            message=Message(
                query="",
                resource_kind=data.resource_kind,
                resource_name=data.resource_name,
                resource_api_version=data.resource_api_version,
                namespace=data.namespace,
            ),
        )

        # Return response with session_id in the header.
        response = InitialQuestionsResponse(
            initial_questions=questions, conversation_id=session_id
        )
        return JSONResponse(
            content=jsonable_encoder(response),
            headers={SESSION_ID_HEADER: session_id},
        )
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{conversation_id}/questions", response_model=FollowUpQuestionsResponse)
async def followup_questions(
    conversation_id: Annotated[str, Path(title="The ID of the conversation")],
    service: IService = Depends(get_conversation_service),  # noqa B008
) -> JSONResponse:
    """Endpoint to generate follow-up questions for a conversation."""

    try:
        # Create follow-up questions.
        questions = await service.handle_followup_questions(
            conversation_id=conversation_id
        )

        # Return response.
        response = FollowUpQuestionsResponse(
            questions=questions,
        )
        return JSONResponse(
            content=jsonable_encoder(response),
        )
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/{conversation_id}/messages")
async def messages(
    conversation_id: Annotated[
        str, Path(title="The ID of the conversation to continue")
    ],
    message: Annotated[Message, Body(title="The message to send")],
    x_cluster_url: Annotated[str, Header()],
    x_k8s_authorization: Annotated[str, Header()],
    x_cluster_certificate_authority_data: Annotated[str, Header()],
    service: IService = Depends(get_conversation_service),  # noqa B008
) -> StreamingResponse:
    """Endpoint to send a message to the Kyma companion"""

    # Check rate limitation
    if TOKEN_LIMIT_PER_CLUSTER != -1:
        from_timestamp, to_timestamp = get_current_day_timestamps_utc()
        hashed_cluster_url = hash_url(x_cluster_url)
        langfuse_api = LangfuseAPI()
        total_token_usage = langfuse_api.get_total_token_usage(from_timestamp, to_timestamp, hashed_cluster_url)

        if total_token_usage > TOKEN_LIMIT_PER_CLUSTER:
            current_utc = datetime.now(UTC)
            midnight_utc = current_utc.replace(hour=23, minute=59, second=59)
            time_remaining = midnight_utc - current_utc
            seconds_remaining = int(time_remaining.total_seconds())
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "message": f"Daily token limit of {TOKEN_LIMIT_PER_CLUSTER} exceeded for this cluster",
                    "current_usage": total_token_usage,
                    "limit": TOKEN_LIMIT_PER_CLUSTER,
                    "time_remaining_seconds": seconds_remaining
                },
                headers={
                    "Retry-After": str(seconds_remaining),
                    "X-RateLimit-Limit": str(TOKEN_LIMIT_PER_CLUSTER),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(midnight_utc.timestamp()))
                }
            )

    # Initialize k8s client for the request.
    try:
        k8s_client: IK8sClient = K8sClient(
            api_server=x_cluster_url,
            user_token=x_k8s_authorization,
            certificate_authority_data=x_cluster_certificate_authority_data,
        )
    except Exception as e:
        logger.error(e)
        raise HTTPException(
            status_code=400, detail=f"failed to connect to the cluster: {str(e)}"
        ) from e

    return StreamingResponse(
        (
            prepare_chunk_response(chunk) + b"\n"
            async for chunk in service.handle_request(
                conversation_id, message, k8s_client
            )
        ),
        media_type="text/event-stream",
    )
