from http import HTTPStatus
from typing import Annotated, Protocol

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from routers.common import API_PREFIX
from services.redis import get_redis
from utils.logging import get_logger
from utils.settings import ENCRYPTION_PUBLIC_KEY_B64, REDIS_TTL
from utils.utils import create_session_id

logger = get_logger(__name__)


class IRedisConnection(Protocol):
    async def set(self, name: str, value: str, ex: int | None = None) -> bool:
        ...


class IRedisService(Protocol):
    def get_connection(self) -> IRedisConnection:
        ...


class PublicKeyRequest(BaseModel):
    """Request model for storing a client public key for a session."""

    public_key: str = Field(..., min_length=1, description="Client public key")


class PublicKeyResponse(BaseModel):
    """Response model for public key initialization endpoint."""

    session_id: str
    companion_public_key: str


router = APIRouter(
    prefix=API_PREFIX,
    tags=["encryption"],
)


def _get_client_public_key() -> str:
    """Return companion public key configured for key exchange."""
    if not ENCRYPTION_PUBLIC_KEY_B64:
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Companion public key is not configured",
        )
    return str(ENCRYPTION_PUBLIC_KEY_B64)


@router.post("/public-key", response_model=PublicKeyResponse)
async def init_public_key(
    request: Annotated[PublicKeyRequest, Body()],
    redis: Annotated[IRedisService, Depends(get_redis)],
) -> PublicKeyResponse:
    """Initialize a key exchange session by storing client public key in Redis."""

    session_id = create_session_id()

    try:
        await redis.get_connection().set(name=session_id, value=request.public_key, ex=REDIS_TTL)
    except Exception as e:
        logger.error(f"Failed to persist client public key in Redis: {str(e)}")
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Failed to initialize public key exchange session",
        ) from e

    return PublicKeyResponse(
        session_id=session_id,
        companion_public_key=_get_client_public_key(),
    )