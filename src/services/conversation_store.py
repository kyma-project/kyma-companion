"""Simple Redis message store for conversation history and thread ownership."""

from __future__ import annotations

import json
from typing import Protocol

from redis.asyncio import Redis as AsyncRedis

from services.redis import Redis
from utils.logging import get_logger
from utils.settings import REDIS_TTL

logger = get_logger(__name__)


class IConversationStore(Protocol):
    """Interface for conversation message storage."""

    async def load_messages(self, conversation_id: str) -> list[dict]:
        """Load all messages for a conversation."""
        ...

    async def save_messages(self, conversation_id: str, messages: list[dict]) -> None:
        """Save messages for a conversation (replaces existing)."""
        ...

    async def get_thread_owner(self, conversation_id: str) -> str | None:
        """Get the owner of a conversation thread."""
        ...

    async def set_thread_owner(self, conversation_id: str, owner: str) -> None:
        """Set the owner of a conversation thread."""
        ...


class ConversationStore:
    """Redis-backed conversation message store."""

    def __init__(self, conn: AsyncRedis | None = None, ttl: int = REDIS_TTL):
        self._conn = conn or Redis().get_connection()
        self._ttl = ttl

    def _messages_key(self, conversation_id: str) -> str:
        return f"conv:{conversation_id}:messages"

    def _owner_key(self, conversation_id: str) -> str:
        return f"conv:{conversation_id}:owner"

    async def load_messages(self, conversation_id: str) -> list[dict]:
        """Load all messages for a conversation."""
        key = self._messages_key(conversation_id)
        data = await self._conn.get(key)
        if data is None:
            return []
        result: list[dict] = json.loads(data)
        return result

    async def save_messages(self, conversation_id: str, messages: list[dict]) -> None:
        """Save messages for a conversation (replaces existing)."""
        key = self._messages_key(conversation_id)
        await self._conn.set(key, json.dumps(messages), ex=self._ttl)

    async def get_thread_owner(self, conversation_id: str) -> str | None:
        """Get the owner of a conversation thread."""
        key = self._owner_key(conversation_id)
        owner = await self._conn.get(key)
        if owner is None:
            return None
        return owner.decode() if isinstance(owner, bytes) else str(owner)

    async def set_thread_owner(self, conversation_id: str, owner: str) -> None:
        """Set the owner of a conversation thread."""
        key = self._owner_key(conversation_id)
        await self._conn.set(key, owner, ex=self._ttl)
