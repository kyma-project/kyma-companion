"""Redis-backed LLM usage memory."""

import json
import time
from typing import Protocol

from redis.asyncio import Redis as AsyncRedis


class IUsageMemory(Protocol):
    """Interface for LLM token usage memory."""

    async def awrite_llm_usage(self, cluster_id: str, data: dict, ttl: int = 0) -> str:
        """Write LLM usage data to Redis. Return the key."""

    async def adelete_expired_llm_usage_records(self, cluster_id: str, ttl: int) -> None:
        """Delete expired LLM usage records."""

    async def alist_llm_usage_records(self, cluster_id: str, ttl: int) -> list[dict]:
        """List non-expired LLM usage records."""


def _get_llm_usage_key_prefix(cluster_id: str) -> str:
    """Get the Redis key prefix for LLM usage data."""
    return f"llm_usage_{cluster_id}"


def _make_llm_usage_key(cluster_id: str) -> str:
    """Create a Redis key for storing LLM usage data."""
    return f"{_get_llm_usage_key_prefix(cluster_id)}_{time.time()}"


def _get_llm_usage_key_filter(cluster_id: str) -> str:
    """Get the Redis key filter for LLM usage data."""
    return f"{_get_llm_usage_key_prefix(cluster_id)}_*"


def _extract_time_from_llm_usage_key(key: str) -> float:
    """Extract the timestamp from an LLM usage key."""
    return float(key.split("_")[-1])


def _safe_decode(key: str | bytes) -> str:
    """Safely decode a key that might be bytes or str."""
    return key.decode() if isinstance(key, bytes) else key


class AsyncRedisSaver:
    """Redis-backed LLM usage tracker."""

    conn: AsyncRedis

    def __init__(self, conn: AsyncRedis):
        self.conn = conn

    async def awrite_llm_usage(self, cluster_id: str, data: dict, ttl: int = 0) -> str:
        """Write LLM usage data to Redis. Return the key."""
        key = _make_llm_usage_key(cluster_id)
        if ttl > 0:
            await self.conn.set(key, json.dumps(data), ex=ttl)
        else:
            await self.conn.set(key, json.dumps(data))
        return key

    async def adelete_expired_llm_usage_records(self, cluster_id: str, ttl: int) -> None:
        """Delete expired LLM usage records."""
        keys = await self.conn.keys(_get_llm_usage_key_filter(cluster_id))
        keys_to_delete = []
        for key in keys:
            old_time = _extract_time_from_llm_usage_key(_safe_decode(key))
            if time.time() - old_time > ttl:
                keys_to_delete.append(key)
        if len(keys_to_delete) > 0:
            await self.conn.delete(*keys_to_delete)

    async def alist_llm_usage_records(self, cluster_id: str, ttl: int) -> list[dict]:
        """List non-expired LLM usage records."""
        keys = await self.conn.keys(_get_llm_usage_key_filter(cluster_id))
        latest_keys = []
        for key in keys:
            old_time = _extract_time_from_llm_usage_key(_safe_decode(key))
            if time.time() - old_time < ttl:
                latest_keys.append(key)
        records = await self.conn.mget(latest_keys)
        return [json.loads(record) for record in records if record]
