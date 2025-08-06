from functools import lru_cache
from http import HTTPStatus
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Path
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse, StreamingResponse

from agents.common.constants import CLUSTER, ERROR_RATE_LIMIT_CODE, UNKNOWN
from agents.common.data import Message
from agents.common.utils import compute_string_token_count
from routers.common import (
    API_PREFIX,
    SESSION_ID_HEADER,
    FollowUpQuestionsResponse,
    InitConversationBody,
    InitialQuestionsResponse,
)
from services.conversation import ConversationService, IService
from services.data_sanitizer import DataSanitizer, IDataSanitizer
from services.k8s import IK8sClient, K8sAuthHeaders, K8sClient
from services.k8s_resource_discovery import K8sResourceDiscovery
from services.langfuse import ILangfuseService, LangfuseService
from utils.config import Config, get_config
from utils.logging import get_logger
from utils.response import prepare_chunk_response
from utils.settings import MAIN_MODEL_NAME, MAX_TOKEN_LIMIT_INPUT_QUERY
from utils.utils import (
    create_session_id,
    get_user_identifier_from_client_certificate,
    get_user_identifier_from_token,
)

logger = get_logger(__name__)


def get_langfuse_service() -> ILangfuseService:
    """Dependency to get the langfuse service instance."""
    return LangfuseService()


@lru_cache(maxsize=1)
def init_config() -> Config:
    """Initialize the config object once."""
    return get_config()


def init_data_sanitizer(
    config: Annotated[Config, Depends(init_config)],
) -> IDataSanitizer:
    """Initialize the data sanitizer instance"""
    return DataSanitizer(config.sanitization_config)


def init_conversation_service(
    config: Annotated[Config, Depends(init_config)],
    langfuse_service: ILangfuseService = Depends(get_langfuse_service),  # noqa B008
) -> IService:
    """Initialize the conversation service instance"""
    return ConversationService(langfuse_handler=langfuse_service.handler, config=config)


def enforce_query_token_limit(
    message: Annotated[
        Message | InitConversationBody | None,
        Body(title="The payload which may be either a Message or InitConversationBody"),
    ] = None,
) -> None:
    """Enforce query token limit to input request."""
    if message is None:
        return
    token_count = compute_string_token_count(message.model_dump_json(), MAIN_MODEL_NAME)
    logger.info(f"Input Query Token count is {token_count}")
    if token_count > MAX_TOKEN_LIMIT_INPUT_QUERY:
        raise HTTPException(
            status_code=400, detail="Input Query exceeds the allowed token limit."
        )


router = APIRouter(
    prefix=f"{API_PREFIX}/conversations",
    tags=["conversations"],
)


@router.post("/", response_model=InitialQuestionsResponse)
async def init_conversation(
    message: InitConversationBody,
    x_cluster_url: Annotated[str, Header()],
    x_cluster_certificate_authority_data: Annotated[str, Header()],
    conversation_service: Annotated[IService, Depends(init_conversation_service)],
    data_sanitizer: Annotated[IDataSanitizer, Depends(init_data_sanitizer)],
    session_id: Annotated[str, Header()] = "",
    x_k8s_authorization: Annotated[str, Header()] = None,  # type: ignore[assignment]
    x_client_certificate_data: Annotated[str, Header()] = None,  # type: ignore[assignment]
    x_client_key_data: Annotated[str, Header()] = None,  # type: ignore[assignment]
    _: Annotated[None, Depends(enforce_query_token_limit)] = None,
) -> JSONResponse:
    """Endpoint to initialize a conversation with Kyma Companion and generates initial questions."""

    logger.info(
        f"Initializing new conversation. Request data: {message.model_dump_json()}"
    )

    # Validate if all the required K8s headers are provided.
    k8s_auth_headers = K8sAuthHeaders(
        x_cluster_url=x_cluster_url,
        x_cluster_certificate_authority_data=x_cluster_certificate_authority_data,
        x_k8s_authorization=x_k8s_authorization,
        x_client_certificate_data=x_client_certificate_data,
        x_client_key_data=x_client_key_data,
    )
    try:
        k8s_auth_headers.validate_headers()
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    # Initialize with the session_id. Create a new session_id if not provided.
    session_id = session_id if session_id else create_session_id()

    # Initialize k8s client for the request.
    try:
        k8s_client: IK8sClient = K8sClient(
            k8s_auth_headers=k8s_auth_headers,
            data_sanitizer=data_sanitizer,
        )
    except Exception as e:
        logger.error(e)
        raise HTTPException(
            status_code=400, detail=f"failed to connect to the cluster: {str(e)}"
        ) from e

    # Check rate limitation
    await check_token_usage(x_cluster_url, conversation_service)

    try:
        # Create initial questions.
        questions = conversation_service.new_conversation(
            k8s_client=k8s_client,
            message=Message(
                query="",
                resource_kind=message.resource_kind,
                resource_name=message.resource_name,
                resource_api_version=message.resource_api_version,
                namespace=message.namespace,
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
        raise HTTPException(
            status_code=500,
            detail=f"{str(e)}, Request data: {message.model_dump_json()}",
        ) from e


@router.get("/{conversation_id}/questions", response_model=FollowUpQuestionsResponse)
async def followup_questions(
    conversation_id: Annotated[UUID, Path(title="The ID of the conversation")],
    x_cluster_url: Annotated[str, Header()],
    x_cluster_certificate_authority_data: Annotated[str, Header()],
    conversation_service: Annotated[IService, Depends(init_conversation_service)],
    x_k8s_authorization: Annotated[str, Header()] = None,  # type: ignore[assignment]
    x_client_certificate_data: Annotated[str, Header()] = None,  # type: ignore[assignment]
    x_client_key_data: Annotated[str, Header()] = None,  # type: ignore[assignment]
) -> JSONResponse:
    """Endpoint to generate follow-up questions for a conversation."""

    # Validate if all the required K8s headers are provided.
    k8s_auth_headers = K8sAuthHeaders(
        x_cluster_url=x_cluster_url,
        x_cluster_certificate_authority_data=x_cluster_certificate_authority_data,
        x_k8s_authorization=x_k8s_authorization,
        x_client_certificate_data=x_client_certificate_data,
        x_client_key_data=x_client_key_data,
    )
    try:
        k8s_auth_headers.validate_headers()
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    # Authorize the user to access the conversation.
    user_identifier = extract_user_identifier(k8s_auth_headers)
    await authorize_user(str(conversation_id), user_identifier, conversation_service)

    # Check rate limitation
    await check_token_usage(x_cluster_url, conversation_service)

    try:
        # Create follow-up questions.
        questions = await conversation_service.handle_followup_questions(
            conversation_id=str(conversation_id)
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
        UUID, Path(title="The ID of the conversation to continue")
    ],
    message: Annotated[Message, Body(title="The message to send")],
    x_cluster_url: Annotated[str, Header()],
    x_cluster_certificate_authority_data: Annotated[str, Header()],
    conversation_service: Annotated[IService, Depends(init_conversation_service)],
    data_sanitizer: Annotated[IDataSanitizer, Depends(init_data_sanitizer)],
    x_k8s_authorization: Annotated[str, Header()] = None,  # type: ignore[assignment]
    x_client_certificate_data: Annotated[str, Header()] = None,  # type: ignore[assignment]
    x_client_key_data: Annotated[str, Header()] = None,  # type: ignore[assignment]
    _: Annotated[None, Depends(enforce_query_token_limit)] = None,
) -> StreamingResponse:
    """Endpoint to send a message to the Kyma companion"""

    logger.info(
        f"Handling conversation: {str(conversation_id)}. Request data: {message.model_dump_json()}"
    )

    # Validate if all the required K8s headers are provided.
    k8s_auth_headers = K8sAuthHeaders(
        x_cluster_url=x_cluster_url,
        x_cluster_certificate_authority_data=x_cluster_certificate_authority_data,
        x_k8s_authorization=x_k8s_authorization,
        x_client_certificate_data=x_client_certificate_data,
        x_client_key_data=x_client_key_data,
    )
    try:
        k8s_auth_headers.validate_headers()
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e

    # Authorize the user to access the conversation.
    message.user_identifier = extract_user_identifier(k8s_auth_headers)
    await authorize_user(
        str(conversation_id), message.user_identifier, conversation_service
    )

    # Check rate limitation
    await check_token_usage(x_cluster_url, conversation_service)

    # Initialize k8s client for the request.
    try:
        k8s_client: IK8sClient = K8sClient.new(
            k8s_auth_headers=k8s_auth_headers,
            data_sanitizer=data_sanitizer,
        )
    except Exception as e:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"failed to connect to the cluster: {str(e)}",
        ) from e

    # Validate the k8s resource context.
    if not message.is_cluster_overview_query():
        try:
            resource_kind_details = K8sResourceDiscovery(k8s_client).get_resource_kind(
                str(message.resource_api_version), str(message.resource_kind)
            )
            # Add details to the message.
            message.add_details(resource_kind_details)
        except Exception as e:
            logger.warning(f"Invalid resource context info: {str(e)}")
            message.resource_kind = UNKNOWN
            message.resource_api_version = UNKNOWN
    else:
        # mark the message as a cluster overview query
        message.resource_scope = CLUSTER

    return StreamingResponse(
        (
            chunk_response + b"\n"
            async for chunk in conversation_service.handle_request(
                str(conversation_id), message, k8s_client
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
                "error": "Token usage limit exceeded",
                "message": f"Token usage limit of {report.token_limit} exceeded for this cluster. "
                f"To ensure a fair usage, Joule controls the number"
                f" of requests a cluster can make within 24 hours.",
                "current_usage": report.total_tokens_used,
                "limit": report.token_limit,
                "time_remaining_seconds": report.reset_seconds_left,
            },
            headers={"Retry-After": str(report.reset_seconds_left)},
        )


def extract_user_identifier(
    k8s_auth_headers: K8sAuthHeaders,
) -> str:
    """Get the user identifier from the K8s auth headers."""
    user_identifier = ""
    if k8s_auth_headers.x_k8s_authorization is not None:
        try:
            user_identifier = get_user_identifier_from_token(
                k8s_auth_headers.x_k8s_authorization
            )
        except Exception as e:
            logger.error(e)
            raise HTTPException(status_code=401, detail="Invalid token") from e
    elif k8s_auth_headers.x_client_certificate_data is not None:
        try:
            user_identifier = get_user_identifier_from_client_certificate(
                k8s_auth_headers.get_decoded_client_certificate_data()
            )
        except Exception as e:
            logger.error(e)
            raise HTTPException(
                status_code=401, detail="Invalid client certificate"
            ) from e

    if user_identifier == "":
        raise HTTPException(
            status_code=401,
            detail="User not authorized to access the conversation. "
            "Unable to get user identifier from the provided Authorization headers.",
        )

    return user_identifier


async def authorize_user(
    conversation_id: str,
    user_identifier: str,
    conversation_service: IService,
) -> None:
    """Authorize the user to access the conversation."""

    if not await conversation_service.authorize_user(conversation_id, user_identifier):
        raise HTTPException(
            status_code=403, detail="User not authorized to access the conversation"
        )
