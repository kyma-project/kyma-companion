import json
from collections.abc import AsyncGenerator
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, HTTPException, Path
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse, StreamingResponse

from agents.common.data import Message
from routers.common import (
    API_PREFIX,
    SESSION_ID_HEADER,
    InitConversationBody,
    InitialQuestionsResponse,
)
from services.conversation import ConversationService, IService
from services.k8s import IK8sClient, K8sClient
from utils.logging import get_logger
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
) -> dict:
    """Endpoint to initialize a conversation with Kyma Companion and generates initial questions."""
    logger.info("Initializing new conversation.")

    # initialize with the session_id. Create a new session_id if not provided.
    conversation_id = create_session_id()
    if session_id != "":
        conversation_id = session_id

    # initialize k8s client for the request.
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
        service = get_conversation_service()
        questions = await service.new_conversation(
            conversation_id,
            Message(
                query="",
                resource_kind=data.resource_kind,
                resource_name=data.resource_name,
                resource_api_version=data.resource_api_version,
                namespace=data.namespace,
            ),
            k8s_client=k8s_client,
        )

        # return response with session_id in the header.
        response = InitialQuestionsResponse(
            initial_questions=questions, conversation_id=conversation_id
        )
        return JSONResponse(
            content=jsonable_encoder(response),
            headers={SESSION_ID_HEADER: conversation_id},
        )
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=str(e)) from e


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
