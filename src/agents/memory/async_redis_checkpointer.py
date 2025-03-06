"""Implementation of a langgraph checkpoint saver using Redis."""

import json
import time
from collections.abc import AsyncGenerator, Awaitable, Sequence
from typing import (
    Any,
    Protocol,
    TypeVar,
)

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    PendingWrite,
    get_checkpoint_id,
)
from langgraph.checkpoint.serde.base import SerializerProtocol
from redis.asyncio import Redis as AsyncRedis

from utils.settings import REDIS_TTL

REDIS_KEY_SEPARATOR = "$"

T = TypeVar("T")


# Interfaces


class IUsageMemory(Protocol):
    """Interface for LLM token usage memory."""

    async def awrite_llm_usage(self, cluster_id: str, data: dict, ttl: int = 0) -> str:
        """Write LLM usage data to Redis. Return the key."""

    async def adelete_expired_llm_usage_records(
        self, cluster_id: str, ttl: int
    ) -> None:
        """Delete expired LLM usage records."""

    async def alist_llm_usage_records(self, cluster_id: str, ttl: int) -> list[dict]:
        """List non-expired LLM usage records."""


# Utilities shared by both RedisSaver and AsyncRedisSaver


def _make_redis_checkpoint_key(
    thread_id: str, checkpoint_ns: str, checkpoint_id: str
) -> str:
    """Create a Redis key for storing checkpoint data.

    Returns a Redis key string in the format "checkpoint$thread_id$namespace$checkpoint_id".
    """
    return REDIS_KEY_SEPARATOR.join(
        ["checkpoint", thread_id, checkpoint_ns, checkpoint_id]
    )


def _make_redis_checkpoint_writes_key(
    thread_id: str,
    checkpoint_ns: str,
    checkpoint_id: str,
    task_id: str,
    idx: int | None,
) -> str:
    """Create a Redis key for storing checkpoint writes data.

    Returns a Redis key string in the format "writes$thread_id$namespace$checkpoint_id$task_id$idx".
    """
    if idx is None:
        return REDIS_KEY_SEPARATOR.join(
            ["writes", thread_id, checkpoint_ns, checkpoint_id, task_id]
        )

    return REDIS_KEY_SEPARATOR.join(
        ["writes", thread_id, checkpoint_ns, checkpoint_id, task_id, str(idx)]
    )


def _parse_redis_checkpoint_key(redis_key: str) -> dict:
    """Parse a Redis checkpoint key.

    Returns a dictionary containing the parsed checkpoint data.
    """
    namespace, thread_id, checkpoint_ns, checkpoint_id = redis_key.split(
        REDIS_KEY_SEPARATOR
    )
    if namespace != "checkpoint":
        raise ValueError("Expected checkpoint key to start with 'checkpoint'")

    return {
        "thread_id": thread_id,
        "checkpoint_ns": checkpoint_ns,
        "checkpoint_id": checkpoint_id,
    }


def _parse_redis_checkpoint_writes_key(redis_key: str) -> dict:
    """Parse a Redis checkpoint writes key.

    Returns a dictionary containing the parsed checkpoint writes data.
    """
    namespace, thread_id, checkpoint_ns, checkpoint_id, task_id, idx = redis_key.split(
        REDIS_KEY_SEPARATOR
    )
    if namespace != "writes":
        raise ValueError("Expected checkpoint key to start with 'checkpoint'")

    return {
        "thread_id": thread_id,
        "checkpoint_ns": checkpoint_ns,
        "checkpoint_id": checkpoint_id,
        "task_id": task_id,
        "idx": idx,
    }


def _safe_decode(key: str | bytes) -> str:
    """Safely decode a key that might be bytes or str."""
    return key.decode() if isinstance(key, bytes) else key


def _filter_keys(
    keys: list[str | bytes], before: RunnableConfig | None, limit: int | None
) -> list[str | bytes]:
    """
    Filter and sort Redis keys based on optional criteria.
    Returns list of filtered and sorted Redis keys.
    """
    if before:
        keys = [
            k
            for k in keys
            if _parse_redis_checkpoint_key(_safe_decode(k))["checkpoint_id"]
            < before["configurable"]["checkpoint_id"]
        ]

    keys = sorted(
        keys,
        key=lambda k: _parse_redis_checkpoint_key(_safe_decode(k))["checkpoint_id"],
        reverse=True,
    )
    if limit:
        keys = keys[:limit]
    return keys


def _load_writes(
    serde: SerializerProtocol, task_id_to_data: dict[tuple[str, str], dict]
) -> list[PendingWrite]:
    """Deserialize pending writes."""
    writes = [
        (
            task_id,
            data[b"channel"].decode(),
            serde.loads_typed((data[b"type"].decode(), data[b"value"])),
        )
        for (task_id, _), data in task_id_to_data.items()
    ]
    return writes


def _parse_redis_checkpoint_data(
    serde: SerializerProtocol,
    key: str,
    data: dict[bytes, bytes],
    pending_writes: list[PendingWrite] | None = None,
) -> CheckpointTuple | None:
    """Parse checkpoint data retrieved from Redis."""
    if not data:
        return None

    parsed_key = _parse_redis_checkpoint_key(key)
    thread_id = parsed_key["thread_id"]
    checkpoint_ns = parsed_key["checkpoint_ns"]
    checkpoint_id = parsed_key["checkpoint_id"]
    config: RunnableConfig = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
            "checkpoint_id": checkpoint_id,
        }
    }

    checkpoint = serde.loads_typed((data[b"type"].decode(), data[b"checkpoint"]))
    metadata = serde.loads(data[b"metadata"])
    parent_checkpoint_id = data.get(b"parent_checkpoint_id", b"").decode()
    parent_config: RunnableConfig | None = (
        {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": parent_checkpoint_id,
            }
        }
        if parent_checkpoint_id
        else None
    )
    return CheckpointTuple(
        config=config,
        checkpoint=checkpoint,
        metadata=metadata,
        parent_config=parent_config,
        pending_writes=pending_writes,
    )


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


class AsyncRedisSaver(BaseCheckpointSaver):
    """Async redis-based checkpoint saver implementation."""

    conn: AsyncRedis

    def __init__(self, conn: AsyncRedis):
        super().__init__()
        self.conn = conn

    @classmethod
    def from_conn_info(
        cls, *, host: str, port: int, db: int, password: str
    ) -> "AsyncRedisSaver":
        """Create a new AsyncRedisSaver with the given connection info.

        This is a synchronous method that will fail fast if Redis connection cannot be established.
        """
        conn = AsyncRedis(
            host=host, port=port, db=db, password=password if password != "" else None
        )
        return cls(conn)

    async def _redis_call(self, awaitable: Awaitable[T] | T) -> T:
        """Helper method to handle Redis async calls that may return Awaitable[T] | T."""
        if isinstance(awaitable, Awaitable):
            return await awaitable
        return awaitable

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
        redis_ttl: int = REDIS_TTL,
    ) -> RunnableConfig:
        """Save a checkpoint to the database asynchronously.

        This method saves a checkpoint to Redis. The checkpoint is associated
        with the provided config and its parent config (if any).

        Args:
            config (RunnableConfig): The config to associate with the checkpoint.
            checkpoint (Checkpoint): The checkpoint to save.
            metadata (CheckpointMetadata): Additional metadata to save with the checkpoint.
            new_versions (ChannelVersions): New channel versions as of this write.
            redis_ttl (Int): Time to live for the Redis checkpoint.

        Returns:
            RunnableConfig: Updated configuration after storing the checkpoint.
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"]["checkpoint_ns"]
        checkpoint_id = checkpoint["id"]
        parent_checkpoint_id = config["configurable"].get("checkpoint_id")
        key = _make_redis_checkpoint_key(thread_id, checkpoint_ns, checkpoint_id)

        type_, serialized_checkpoint = self.serde.dumps_typed(checkpoint)
        serialized_metadata = self.serde.dumps(metadata)
        data = {
            "checkpoint": serialized_checkpoint,
            "type": type_,
            "checkpoint_id": checkpoint_id,
            "metadata": serialized_metadata,
            "parent_checkpoint_id": (
                parent_checkpoint_id if parent_checkpoint_id else ""
            ),
        }

        await self._redis_call(self.conn.hset(key, mapping=data))
        # Set TTL for each checkpoint
        await self._redis_call(self.conn.expire(key, redis_ttl))
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
        redis_ttl: int = REDIS_TTL,
    ) -> None:
        """Store intermediate writes linked to a checkpoint asynchronously.

        This method saves intermediate writes associated with a checkpoint to the database.

        Args:
            config (RunnableConfig): Configuration of the related checkpoint.
            writes (Sequence[Tuple[str, Any]]): List of writes to store, each as (channel, value) pair.
            task_id (str): Identifier for the task creating the writes.
            redis_ttl (Int): Time to live for the writes.
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"]["checkpoint_ns"]
        checkpoint_id = config["configurable"]["checkpoint_id"]

        for idx, (channel, value) in enumerate(writes):
            key = _make_redis_checkpoint_writes_key(
                thread_id,
                checkpoint_ns,
                checkpoint_id,
                task_id,
                WRITES_IDX_MAP.get(channel, idx),
            )
            type_, serialized_value = self.serde.dumps_typed(value)
            data = {"channel": channel, "type": type_, "value": serialized_value}
            if all(w[0] in WRITES_IDX_MAP for w in writes):
                # Use HSET which will overwrite existing values
                await self._redis_call(self.conn.hset(key, mapping=data))
            else:
                # Use HSETNX which will not overwrite existing values
                for field, value in data.items():
                    await self._redis_call(self.conn.hsetnx(key, field, value))
            # Set TTL for each write
            await self._redis_call(self.conn.expire(key, redis_ttl))

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """Get a checkpoint tuple from Redis asynchronously.

        This method retrieves a checkpoint tuple from Redis based on the
        provided config. If the config contains a "checkpoint_id" key, the checkpoint with
        the matching thread ID and checkpoint ID is retrieved. Otherwise, the latest checkpoint
        for the given thread ID is retrieved.

        Args:
            config (RunnableConfig): The config to use for retrieving the checkpoint.

        Returns:
            Optional[CheckpointTuple]: The retrieved checkpoint tuple, or None if no matching checkpoint was found.
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_id = get_checkpoint_id(config)
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")

        checkpoint_key = await self._aget_checkpoint_key(
            self.conn, thread_id, checkpoint_ns, checkpoint_id
        )
        if not checkpoint_key:
            return None
        checkpoint_data = await self._redis_call(self.conn.hgetall(checkpoint_key))

        # load pending writes
        checkpoint_id = (
            checkpoint_id
            or _parse_redis_checkpoint_key(checkpoint_key)["checkpoint_id"]
        )
        pending_writes = await self._aload_pending_writes(
            thread_id, checkpoint_ns, checkpoint_id
        )
        return _parse_redis_checkpoint_data(
            self.serde, checkpoint_key, checkpoint_data, pending_writes=pending_writes
        )

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncGenerator[CheckpointTuple, None]:
        """List checkpoints from Redis asynchronously.

        This method retrieves a list of checkpoint tuples from Redis based
        on the provided config. The checkpoints are ordered by checkpoint ID in descending order (newest first).

        Args:
            config (Optional[RunnableConfig]): Base configuration for filtering checkpoints.
            filter (Optional[Dict[str, Any]]): Additional filtering criteria for metadata.
            before (Optional[RunnableConfig]): If provided, only checkpoints before
            the specified checkpoint ID are returned. Defaults to None.
            limit (Optional[int]): Maximum number of checkpoints to return.

        Yields:
            AsyncIterator[CheckpointTuple]: An asynchronous iterator of matching checkpoint tuples.
        """
        if config is None:
            raise ValueError("Config is required")
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        pattern = _make_redis_checkpoint_key(thread_id, checkpoint_ns, "*")
        keys = _filter_keys(await self.conn.keys(pattern), before, limit)
        for key in keys:
            data = await self._redis_call(self.conn.hgetall(_safe_decode(key)))
            if data and b"checkpoint" in data and b"metadata" in data:
                checkpoint_id = _parse_redis_checkpoint_key(_safe_decode(key))[
                    "checkpoint_id"
                ]
                pending_writes = await self._aload_pending_writes(
                    thread_id, checkpoint_ns, checkpoint_id
                )
                if result := _parse_redis_checkpoint_data(
                    self.serde, key.decode(), data, pending_writes=pending_writes
                ):
                    yield result

    async def _aload_pending_writes(
        self, thread_id: str, checkpoint_ns: str, checkpoint_id: str
    ) -> list[PendingWrite]:
        writes_key = _make_redis_checkpoint_writes_key(
            thread_id, checkpoint_ns, checkpoint_id, "*", None
        )
        matching_keys = await self.conn.keys(pattern=writes_key)
        parsed_keys = [
            _parse_redis_checkpoint_writes_key(key.decode()) for key in matching_keys
        ]
        pending_writes = _load_writes(
            self.serde,
            {
                (parsed_key["task_id"], parsed_key["idx"]): await self._redis_call(
                    self.conn.hgetall(key)
                )
                for key, parsed_key in sorted(
                    zip(matching_keys, parsed_keys, strict=False),
                    key=lambda x: x[1]["idx"],
                )
            },
        )
        return pending_writes

    async def _aget_checkpoint_key(
        self,
        conn: AsyncRedis,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str | None,
    ) -> str | None:
        """Asynchronously determine the Redis key for a checkpoint."""
        if checkpoint_id:
            return _make_redis_checkpoint_key(thread_id, checkpoint_ns, checkpoint_id)

        all_keys = await conn.keys(
            _make_redis_checkpoint_key(thread_id, checkpoint_ns, "*")
        )
        if not all_keys:
            return None

        latest_key = max(
            all_keys,
            key=lambda k: _parse_redis_checkpoint_key(_safe_decode(k))["checkpoint_id"],
        )
        return _safe_decode(latest_key)

    async def awrite_llm_usage(self, cluster_id: str, data: dict, ttl: int = 0) -> str:
        """Write LLM usage data to Redis. Return the key."""
        key = _make_llm_usage_key(cluster_id)
        if ttl > 0:
            await self.conn.set(key, json.dumps(data), ex=ttl)
        else:
            await self.conn.set(key, json.dumps(data))
        return key

    async def adelete_expired_llm_usage_records(
        self, cluster_id: str, ttl: int
    ) -> None:
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
