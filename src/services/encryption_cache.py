from typing import Annotated, Protocol

from fastapi import Depends

from services.redis import Redis, get_redis
from utils.settings import REDIS_TTL


class IRedisConnection(Protocol):
    async def set(self, name: str, value: str, ex: int | None = None) -> bool:
        ...


class IRedisService(Protocol):
    def get_connection(self) -> IRedisConnection:
        ...


class EncryptionCache:
    def __init__(self, redis: IRedisService) -> None:
        self._redis = redis

    async def save_public_key(self, session_id: str, public_key: str) -> None:
        await self._redis.get_connection().set(
            name=f"encryption_cache_session_{session_id}",
            value=public_key,
            ex=REDIS_TTL,
        )


def get_encryption_cache(
    redis: Annotated[Redis, Depends(get_redis)],
) -> EncryptionCache:
    return EncryptionCache(redis=redis)