import json
from collections.abc import Awaitable

import redis


class TokenUsageDataValidator:
    """Validator for token usage data in Redis."""

    def __init__(self, redis_url: str):
        self.conn = redis.Redis.from_url(redis_url)

    def __del__(self):
        self.disconnect()

    def disconnect(self) -> None:
        """Disconnect from the Redis server."""
        self.conn.close()

    def fetch_llm_usage_documents(self) -> list[dict]:
        """Fetch all LLM usage documents from Redis."""
        keys = self.conn.keys("llm_usage_*")
        if isinstance(keys, Awaitable):
            raise TypeError(
                "The keys method returned an Awaitable. "
                "Please check the Redis connection and ensure it is not in async mode."
            )
        documents = self.conn.mget(keys)
        return [json.loads(doc) for doc in documents if doc]

    def get_total_token_usage(self) -> int:
        """Get the total token usage from all LLM usage documents."""
        documents = self.fetch_llm_usage_documents()
        return sum([doc["total"] for doc in documents])
