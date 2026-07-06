from typing import Annotated, Protocol, cast, runtime_checkable
from urllib.parse import quote

from fastapi import Depends
from redis.asyncio import Redis as AsyncRedis

from services.redis import Redis, get_redis
from utils.settings import REDIS_TTL

_ENCRYPTION_CACHE_KEY_PREFIX = "encryption:session_id:"
_NONCE_KEY_PREFIX = "encryption:nonce:"


class IRedisService(Protocol):
    """Protocol for services that can provide a Redis connection."""

    def get_connection(self) -> AsyncRedis:
        """Return an active Redis connection."""
        ...


@runtime_checkable
class IEncryptionCache(Protocol):
    """Protocol for services that can store and retrieve session public keys."""

    async def save_client_public_key(self, session_id: str, public_key: str) -> None:
        """Persist a client public key."""
        ...

    async def get_client_public_key(self, session_id: str) -> str | None:
        """Retrieve a client public key, or None if not found."""
        ...

    async def is_nonce_allowed(self, session_id: str, nonce: str) -> bool:
        """Return True if the nonce is allowed (first use or within replay window)."""
        ...


class EncryptionCache:
    """Service for storing encryption-related session data in Redis."""

    def __init__(self, redis: IRedisService) -> None:
        """Initialize the cache with a Redis-backed service."""
        self._redis = redis

    async def save_client_public_key(self, session_id: str, public_key: str) -> None:
        """Persist a client public key in Redis using the configured TTL."""
        await self._redis.get_connection().set(
            name=f"{_ENCRYPTION_CACHE_KEY_PREFIX}{session_id}",
            value=public_key,
            ex=REDIS_TTL,
        )

    async def get_client_public_key(self, session_id: str) -> str | None:
        """Retrieve a client public key from Redis."""
        return cast(
            str | None,
            await self._redis.get_connection().get(
                name=f"{_ENCRYPTION_CACHE_KEY_PREFIX}{session_id}",
            ),
        )

    async def is_nonce_allowed(self, session_id: str, nonce: str) -> bool:
        """Check whether a nonce is allowed for the given session.

        Uses an atomic SET NX (set-if-not-exists) operation so each nonce is
        accepted exactly once. Clients must generate a fresh nonce per request.
        """
        key = f"{_NONCE_KEY_PREFIX}{quote(session_id, safe='')}:{quote(nonce, safe='')}"
        was_set = await self._redis.get_connection().set(key, "1", ex=REDIS_TTL, nx=True)
        return bool(was_set)


def get_encryption_cache(
    redis: Annotated[Redis, Depends(get_redis)],
) -> EncryptionCache:
    """Create an :class:`EncryptionCache` instance for FastAPI dependency injection."""
    return EncryptionCache(redis=redis)
