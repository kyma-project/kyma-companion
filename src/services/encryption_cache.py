from typing import Annotated, Protocol

from fastapi import Depends
from redis.asyncio import Redis as AsyncRedis

from services.redis import Redis, get_redis
from utils.settings import REDIS_TTL


class IRedisService(Protocol):
    """Protocol for services that can provide a Redis connection."""

    def get_connection(self) -> AsyncRedis:
        """Return an active Redis connection."""
        ...


class EncryptionCache:
    """Service for storing encryption-related session data in Redis."""

    def __init__(self, redis: IRedisService) -> None:
        """Initialize the cache with a Redis-backed service."""
        self._redis = redis

    async def save_public_key(self, session_id: str, public_key: str) -> None:
        """Persist a session public key in Redis using the configured TTL."""
        await self._redis.get_connection().set(
            name=f"encryption:session_id:{session_id}",
            value=public_key,
            ex=REDIS_TTL,
        )


def get_encryption_cache(
    redis: Annotated[Redis, Depends(get_redis)],
) -> EncryptionCache:
    """Create an :class:`EncryptionCache` instance for FastAPI dependency injection."""
    return EncryptionCache(redis=redis)
