import json

import redis


class TokenUsageDataValidator:
    def __init__(self, redis_url: str):
        self.conn = redis.Redis.from_url(redis_url)

    def __del__(self):
        self.disconnect()

    def disconnect(self):
        self.conn.close()

    def fetch_llm_usage_documents(self) -> list[dict]:
        keys = self.conn.keys("llm_usage_*")
        documents = self.conn.mget(keys)
        return [json.loads(doc) for doc in documents if doc]

    def get_total_token_usage(self) -> int:
        documents = self.fetch_llm_usage_documents()
        return sum([doc["total"] for doc in documents])
