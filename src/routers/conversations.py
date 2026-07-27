from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException

from agents.common.constants import ERROR_RATE_LIMIT_CODE
from services.conversation import IService
from services.data_sanitizer import DataSanitizer, IDataSanitizer
from services.k8s import K8sAuthHeaders
from utils.config import Config, get_config
from utils.logging import get_logger
from utils.utils import (
    get_user_identifier_from_client_certificate,
    get_user_identifier_from_token,
)

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def init_config() -> Config:
    """Initialize the config object once."""
    return get_config()


def init_data_sanitizer(
    config: Annotated[Config, Depends(init_config)],
) -> IDataSanitizer:
    """Initialize the data sanitizer instance"""
    return DataSanitizer(config.sanitization_config)


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
            user_identifier = get_user_identifier_from_token(k8s_auth_headers.x_k8s_authorization)
        except Exception as e:
            logger.exception("Failed to get user identifier from token")
            raise HTTPException(status_code=401, detail="Invalid token") from e
    elif k8s_auth_headers.x_client_certificate_data is not None:
        try:
            user_identifier = get_user_identifier_from_client_certificate(
                k8s_auth_headers.get_decoded_client_certificate_data()
            )
        except Exception as e:
            logger.exception("Failed to get user identifier from client certificate")
            raise HTTPException(status_code=401, detail="Invalid client certificate") from e

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
        raise HTTPException(status_code=403, detail="User not authorized to access the conversation")
