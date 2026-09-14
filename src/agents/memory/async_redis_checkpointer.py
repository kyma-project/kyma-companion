"""Redis-backed LLM usage memory."""

import json
import time
from typing import Protocol

from redis.asyncio import Redis as AsyncRedis


class IUsageMemory(Protocol):
    """Interface for LLM token usage memory."""

    async def awrite_llm_usage(self, cluster_id: str, data: dict, ttl: int = 0) -> str:
        """Write LLM usage data to Redis. Return the key."""


def _get_llm_usage_key_prefix(cluster_id: str) -> str:
    """Get the Redis key prefix for LLM usage data."""
    return f"llm_usage_{cluster_id}"


def _make_llm_usage_key(cluster_id: str) -> str:
    """Create a Redis key for storing LLM usage data."""
    return f"{_get_llm_usage_key_prefix(cluster_id)}_{time.time()}"


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
