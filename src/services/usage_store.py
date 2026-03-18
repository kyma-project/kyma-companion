"""Extracted token usage tracking store (from AsyncRedisSaver). Implements IUsageMemory."""

from __future__ import annotations

import json
import time
from typing import Protocol

from redis.asyncio import Redis as AsyncRedis

from services.redis import Redis
from utils.logging import get_logger
from utils.settings import REDIS_TTL

logger = get_logger(__name__)


class IUsageMemory(Protocol):
    """Interface for LLM token usage memory."""

    async def awrite_llm_usage(self, cluster_id: str, data: dict, ttl: int = 0) -> str:
        """Write LLM usage data to Redis. Return the key."""
        ...

    async def adelete_expired_llm_usage_records(self, cluster_id: str, ttl: int) -> None:
        """Delete expired LLM usage records."""
        ...

    async def alist_llm_usage_records(self, cluster_id: str, ttl: int) -> list[dict]:
        """List non-expired LLM usage records."""
        ...


def _get_llm_usage_key_prefix(cluster_id: str) -> str:
    return f"llm_usage_{cluster_id}"


def _make_llm_usage_key(cluster_id: str) -> str:
    return f"{_get_llm_usage_key_prefix(cluster_id)}_{time.time()}"


def _get_llm_usage_key_filter(cluster_id: str) -> str:
    return f"{_get_llm_usage_key_prefix(cluster_id)}_*"


def _extract_time_from_llm_usage_key(key: str) -> float:
    return float(key.split("_")[-1])


def _safe_decode(key: str | bytes) -> str:
    return key.decode() if isinstance(key, bytes) else key


class UsageStore:
    """Redis-backed LLM token usage store."""

    def __init__(self, conn: AsyncRedis | None = None):
        self._conn = conn or Redis().get_connection()

    async def awrite_llm_usage(self, cluster_id: str, data: dict, ttl: int = 0) -> str:
        """Write LLM usage data to Redis. Return the key."""
        key = _make_llm_usage_key(cluster_id)
        if ttl > 0:
            await self._conn.set(key, json.dumps(data), ex=ttl)
        else:
            await self._conn.set(key, json.dumps(data))
        return key

    async def adelete_expired_llm_usage_records(self, cluster_id: str, ttl: int) -> None:
        """Delete expired LLM usage records."""
        keys = await self._conn.keys(_get_llm_usage_key_filter(cluster_id))
        keys_to_delete = []
        for key in keys:
            old_time = _extract_time_from_llm_usage_key(_safe_decode(key))
            if time.time() - old_time > ttl:
                keys_to_delete.append(key)
        if keys_to_delete:
            await self._conn.delete(*keys_to_delete)

    async def alist_llm_usage_records(self, cluster_id: str, ttl: int) -> list[dict]:
        """List non-expired LLM usage records."""
        keys = await self._conn.keys(_get_llm_usage_key_filter(cluster_id))
        latest_keys = []
        for key in keys:
            old_time = _extract_time_from_llm_usage_key(_safe_decode(key))
            if time.time() - old_time < ttl:
                latest_keys.append(key)
        if not latest_keys:
            return []
        records = await self._conn.mget(latest_keys)
        return [json.loads(record) for record in records if record]
