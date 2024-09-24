"""Implementation of a langgraph checkpoint saver using Redis."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import (  # noqa UP035
    Any,
    Protocol,
    Sequence,
    Tuple,
)

import redis
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic_core import from_json
from redis.asyncio import ConnectionPool as AsyncConnectionPool
from redis.asyncio import Redis as AsyncRedis

from agents.memory.conversation_history import ConversationMessage
from utils import logging

logger = logging.get_logger(__name__)


class JsonAndBinarySerializer(JsonPlusSerializer):
    """A JSON serializer that can handle binary data."""

    def _default(self, obj: Any) -> Any:
        if isinstance(obj, bytes | bytearray):
            return self._encode_constructor_args(
                obj.__class__, method="fromhex", args=[obj.hex()]
            )
        return super()._default(obj)

    def dumps(self, obj: Any) -> Any:
        """Serialize an object to a string."""
        try:
            if isinstance(obj, bytes | bytearray):
                return obj.hex()
            return super().dumps(obj)
        except Exception as e:
            logger.error(f"Serialization error: {e}")
            raise

    def loads(self, s: Any, is_binary: bool = False) -> Any:
        """Deserialize a string to an object."""
        try:
            if is_binary:
                return bytes.fromhex(s)
            return super().loads(s)
        except Exception as e:
            logger.error(f"Deserialization error: {e}")
            raise


def initialize_async_pool(
    url: str = "redis://localhost", **kwargs: Any
) -> AsyncConnectionPool:
    """Initialize an asynchronous Redis connection pool."""
    try:
        pool = AsyncConnectionPool.from_url(url, **kwargs)
        logger.info(f"Asynchronous Redis pool initialized with url={url}")
        return pool
    except Exception as e:
        logger.error(f"Error initializing async pool: {e}")
        raise


@asynccontextmanager
async def get_async_connection(
    connection: AsyncRedis | AsyncConnectionPool | None,
) -> (AsyncGenerator)[AsyncRedis, None]:
    """Get an asynchronous Redis connection."""
    conn = None
    try:
        if isinstance(connection, AsyncRedis):
            yield connection
        elif isinstance(connection, AsyncConnectionPool):
            conn = AsyncRedis(connection_pool=connection)
            yield conn
        else:
            raise ValueError("Invalid async connection object.")
    except redis.ConnectionError as e:
        logger.error(f"Async connection error: {e}")
        raise
    finally:
        if conn:
            await conn.aclose()


class IMemory(Protocol):
    """Memory Interface."""

    async def add_conversation_message(
        self, conversation_id: str, message: ConversationMessage
    ) -> None:
        """Add a conversation message to the memory."""
        ...

    async def get_all_conversation_messages(
        self, conversation_id: str
    ) -> list[ConversationMessage]:
        """Get all conversation messages from the memory."""
        ...


class RedisSaver(BaseCheckpointSaver):
    """Implementation of a langgraph checkpoint saver using Redis."""

    async_connection: AsyncRedis | AsyncConnectionPool | None = None

    def __init__(
        self, async_connection: AsyncRedis | AsyncConnectionPool | None = None
    ):
        super().__init__(serde=JsonAndBinarySerializer())
        self.async_connection = async_connection

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Saves a checkpoint."""
        thread_id = config["configurable"]["thread_id"]
        parent_ts = config["configurable"].get("thread_ts")
        key = f"checkpoint:{thread_id}:{checkpoint['id']}"
        try:
            async with get_async_connection(self.async_connection) as conn:
                await conn.hset(
                    key,
                    mapping={
                        "checkpoint": self.serde.dumps(checkpoint),
                        "metadata": self.serde.dumps(metadata),
                        "parent_ts": parent_ts if parent_ts else "",
                    },
                )  # type: ignore
                logger.info(
                    f"Checkpoint stored successfully for thread_id: {thread_id}, "
                    f"ts: {checkpoint['ts']}"
                )
        except Exception as e:
            logger.error(f"Failed to aput checkpoint: {e}")
            raise
        return {
            "configurable": {
                "thread_id": thread_id,
                "thread_ts": checkpoint["id"],
            },
        }

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """Gets a checkpoint tuple."""
        thread_id = config["configurable"]["thread_id"]
        thread_ts = config["configurable"].get("thread_ts", None)
        try:
            async with get_async_connection(self.async_connection) as conn:
                if thread_ts:
                    key = f"checkpoint:{thread_id}:{thread_ts}"
                else:
                    all_keys = await conn.keys(f"checkpoint:{thread_id}:*")
                    if not all_keys:
                        logger.info(f"No checkpoints found for thread_id: {thread_id}")
                        return None
                    # convert all_keys to list and sort and get the latest key
                    all_keys.sort(key=lambda k: k.decode())
                    key = all_keys[-1]
                checkpoint_data = await conn.hgetall(key)  # type: ignore
                if not checkpoint_data:
                    logger.info(f"No valid checkpoint data found for key: {key}")
                    return None
                checkpoint = self.serde.loads(checkpoint_data[b"checkpoint"].decode())
                metadata = self.serde.loads(checkpoint_data[b"metadata"].decode())
                parent_ts = checkpoint_data.get(b"parent_ts", b"").decode()
                parent_config = (
                    {"configurable": {"thread_id": thread_id, "thread_ts": parent_ts}}
                    if parent_ts
                    else None
                )
                logger.info(
                    f"Checkpoint retrieved successfully for thread_id: {thread_id}, "
                    f"ts: {thread_ts}"
                )
                return CheckpointTuple(
                    config=config,
                    checkpoint=checkpoint,
                    metadata=metadata,
                    parent_config=parent_config,  # type: ignore
                )
        except Exception as e:
            logger.error(f"Failed to get checkpoint tuple: {e}")
            raise

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[Tuple[str, Any]],  # noqa UP006
        task_id: str,
    ) -> None:
        """Put writes asynchronously."""
        # TODO: let's implement missing checkpointer method later.
        #  Currently, only necessary methods are
        #  implemented.
        return None

    async def add_conversation_message(
        self, conversation_id: str, message: ConversationMessage
    ) -> None:
        """Add a conversation message to the memory.
        Uses Redis Lists: https://redis.io/docs/latest/develop/data-types/lists/"""
        if conversation_id == "":
            raise ValueError("Conversation ID cannot be empty.")

        try:
            async with get_async_connection(self.async_connection) as conn:
                key = f"history:{conversation_id}"
                await conn.lpush(key, message.model_dump_json())  # type: ignore

        except Exception as e:
            raise Exception(f"Failed to add conversation message: {str(e)}") from e

    async def get_all_conversation_messages(
        self, conversation_id: str
    ) -> list[ConversationMessage]:
        """Get all conversation messages from the memory.
        Uses Redis Lists: https://redis.io/docs/latest/develop/data-types/lists/"""
        try:
            async with get_async_connection(self.async_connection) as conn:
                key = f"history:{conversation_id}"
                count = await conn.llen(key)  # type: ignore
                messages = await conn.lrange(key, 0, count)  # type: ignore
                # convert messages to ConversationMessage objects.
                return [from_json(msg, allow_partial=True) for msg in messages]

        except Exception as e:
            raise Exception(f"Failed to get all conversation messages: {str(e)}") from e
