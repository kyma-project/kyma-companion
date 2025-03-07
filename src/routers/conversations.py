from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Path
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse, StreamingResponse

from agents.common.constants import ERROR_RATE_LIMIT_CODE
from agents.common.data import Message
from routers.common import (
    API_PREFIX,
    SESSION_ID_HEADER,
    FollowUpQuestionsResponse,
    InitConversationBody,
    InitialQuestionsResponse,
)
from services.conversation import ConversationService, IService
from services.data_sanitizer import DataSanitizer, IDataSanitizer
from services.k8s import IK8sClient, K8sClient
from services.langfuse import ILangfuseService, LangfuseService
from utils.config import Config, get_config
from utils.logging import get_logger
from utils.response import prepare_chunk_response
from utils.utils import create_session_id, get_user_identifier_from_token

logger = get_logger(__name__)


def get_langfuse_service() -> ILangfuseService:
    """Dependency to get the langfuse service instance"""
    return LangfuseService()


@lru_cache(maxsize=1)
def init_config() -> Config:
    """Initialize the config object once."""
    return get_config()


def init_data_sanitizer(
    config: Annotated[Config, Depends(init_config)]
) -> IDataSanitizer:
    """Initialize the data sanitizer instance"""
    return DataSanitizer(config.sanitization_config)


def init_conversation_service(
    config: Annotated[Config, Depends(init_config)],
    langfuse_service: ILangfuseService = Depends(get_langfuse_service),  # noqa B008
) -> IService:
    """Initialize the conversation service instance"""
    return ConversationService(langfuse_handler=langfuse_service.handler, config=config)


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
    conversation_service: Annotated[IService, Depends(init_conversation_service)],
    data_sanitizer: Annotated[IDataSanitizer, Depends(init_data_sanitizer)],
    session_id: Annotated[str, Header()] = "",
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
            data_sanitizer=data_sanitizer,
        )
    except Exception as e:
        logger.error(e)
        raise HTTPException(
            status_code=400, detail=f"failed to connect to the cluster: {str(e)}"
        ) from e

    try:
        # Create initial questions.
        questions = conversation_service.new_conversation(
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
    x_cluster_url: Annotated[str, Header()],
    x_k8s_authorization: Annotated[str, Header()],
    conversation_service: Annotated[IService, Depends(init_conversation_service)],
) -> JSONResponse:
    """Endpoint to generate follow-up questions for a conversation."""

    # Authorize the user to access the conversation.
    await authorize_user(conversation_id, x_k8s_authorization, conversation_service)

    # Check rate limitation
    await check_token_usage(x_cluster_url, conversation_service)

    try:
        # Create follow-up questions.
        questions = await conversation_service.handle_followup_questions(
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
    conversation_service: Annotated[IService, Depends(init_conversation_service)],
    data_sanitizer: Annotated[IDataSanitizer, Depends(init_data_sanitizer)],
) -> StreamingResponse:
    """Endpoint to send a message to the Kyma companion"""

    # Authorize the user to access the conversation.
    await authorize_user(conversation_id, x_k8s_authorization, conversation_service)

    # Check rate limitation
    await check_token_usage(x_cluster_url, conversation_service)

    # Initialize k8s client for the request.
    try:
        k8s_client: IK8sClient = K8sClient(
            api_server=x_cluster_url,
            user_token=x_k8s_authorization,
            certificate_authority_data=x_cluster_certificate_authority_data,
            data_sanitizer=data_sanitizer,
        )
    except Exception as e:
        logger.error(e)
        raise HTTPException(
            status_code=400, detail=f"failed to connect to the cluster: {str(e)}"
        ) from e

    return StreamingResponse(
        (
            chunk_response + b"\n"
            async for chunk in conversation_service.handle_request(
                conversation_id, message, k8s_client
            )
            for chunk_response in (prepare_chunk_response(chunk),)
            if chunk_response is not None
        ),
        media_type="text/event-stream",
    )


async def check_token_usage(x_cluster_url: str, conversation_service: IService) -> None:
    """Check if the token usage limit is exceeded for the cluster."""
    cluster_id = x_cluster_url.split(".")[1]

    report = await conversation_service.is_usage_limit_exceeded(cluster_id)
    if report is not None:
        raise HTTPException(
            status_code=ERROR_RATE_LIMIT_CODE,
            detail={
                "error": "Rate limit exceeded",
                "message": f"Daily token limit of {report.token_limit} exceeded for this cluster",
                "current_usage": report.total_tokens_used,
                "limit": report.token_limit,
                "time_remaining_seconds": report.reset_seconds_left,
            },
            headers={"Retry-After": str(report.reset_seconds_left)},
        )


async def authorize_user(
    conversation_id: str, x_k8s_authorization: str, conversation_service: IService
) -> None:
    """Authorize the user to access the conversation."""
    try:
        user_identifier = get_user_identifier_from_token(x_k8s_authorization)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=401, detail="Invalid token") from e

    if not await conversation_service.authorize_user(conversation_id, user_identifier):
        raise HTTPException(
            status_code=403, detail="User not authorized to access the conversation"
        )
