import asyncio
from collections import defaultdict
from datetime import UTC, datetime

import fakeredis
import pytest
import pytest_asyncio
from langgraph.checkpoint.base import Checkpoint
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from agents.memory.async_redis_checkpointer import (
    AsyncRedisSaver,
    _make_redis_checkpoint_key,
    _make_redis_checkpoint_writes_key,
    _parse_redis_checkpoint_key,
    _parse_redis_checkpoint_writes_key,
)


def create_checkpoint(checkpoint_id: str) -> Checkpoint:
    return Checkpoint(
        v=1,
        id=checkpoint_id,
        ts=datetime.now(UTC).isoformat(),
        channel_values={},
        channel_versions={},
        versions_seen=defaultdict(dict),
        pending_sends=[],
    )


def create_metadata(step: int) -> dict:
    return {"source": "input", "step": step, "writes": {}, "score": 1}


@pytest.mark.asyncio
class TestAsyncRedisSaver:
    serde = JsonPlusSerializer()

    @pytest_asyncio.fixture
    async def fake_async_redis(self):
        async with fakeredis.FakeAsyncRedis() as client:
            yield client

    @pytest_asyncio.fixture
    def async_redis_saver(self, fake_async_redis):
        return AsyncRedisSaver(conn=fake_async_redis)

    async def test_concurrent_writes(self, async_redis_saver, fake_async_redis):
        config = {
            "configurable": {
                "thread_id": "thread-1",
                "checkpoint_ns": "ns1",
                "checkpoint_id": "chk-1",
            }
        }
        writes1 = [("channel1", "value1")]
        writes2 = [("channel1", "value2")]
        task_id = "task1"

        # Simulate concurrent writes
        await asyncio.gather(
            async_redis_saver.aput_writes(config, writes1, task_id),
            async_redis_saver.aput_writes(config, writes2, task_id),
        )

        key = _make_redis_checkpoint_writes_key(
            config["configurable"]["thread_id"],
            config["configurable"]["checkpoint_ns"],
            config["configurable"]["checkpoint_id"],
            task_id,
            0,
        )
        stored_data = await fake_async_redis.hgetall(key)
        assert b"channel" in stored_data

    @pytest.mark.parametrize(
        "config, writes, task_id, expected_data",
        [
            # Basic write
            (
                {
                    "configurable": {
                        "thread_id": "thread-1",
                        "checkpoint_ns": "ns1",
                        "checkpoint_id": "chk-1",
                    }
                },
                [("channel1", "value1")],
                "task1",
                {"channel": "channel1", "value": "value1"},
            ),
            # Multiple writes
            (
                {
                    "configurable": {
                        "thread_id": "thread-1",
                        "checkpoint_ns": "ns1",
                        "checkpoint_id": "chk-1",
                    }
                },
                [("channel1", "value1"), ("channel2", "value2")],
                "task1",
                {"channel": "channel1", "value": "value1"},  # Check first write
            ),
            # Special characters in channel name
            (
                {
                    "configurable": {
                        "thread_id": "thread-1",
                        "checkpoint_ns": "ns1",
                        "checkpoint_id": "chk-1",
                    }
                },
                [("channel:1", "value1")],
                "task1",
                {"channel": "channel:1", "value": "value1"},
            ),
            # Empty value
            (
                {
                    "configurable": {
                        "thread_id": "thread-1",
                        "checkpoint_ns": "ns1",
                        "checkpoint_id": "chk-1",
                    }
                },
                [("channel1", "")],
                "task1",
                {"channel": "channel1", "value": ""},
            ),
        ],
    )
    async def test_aput_writes(
        self,
        async_redis_saver,
        fake_async_redis,
        config,
        writes,
        task_id,
        expected_data,
    ):
        await async_redis_saver.aput_writes(config, writes, task_id)

        key = _make_redis_checkpoint_writes_key(
            config["configurable"]["thread_id"],
            config["configurable"]["checkpoint_ns"],
            config["configurable"]["checkpoint_id"],
            task_id,
            0,
        )
        stored_data = await fake_async_redis.hgetall(key)
        assert stored_data[b"channel"] == expected_data["channel"].encode()
        # The value is stored with type information by dumps_typed
        assert (
            stored_data[b"value"]
            == async_redis_saver.serde.dumps_typed(expected_data["value"])[1]
        )

    @pytest.mark.parametrize(
        "config, checkpoint_data, expected_result",
        [
            # Basic case
            (
                {
                    "configurable": {
                        "thread_id": "thread-1",
                        "checkpoint_ns": "ns1",
                        "checkpoint_id": "chk-1",
                    }
                },
                {
                    "checkpoint": create_checkpoint("chk-1"),
                    "metadata": create_metadata(1),
                },
                True,
            ),
            # Non-existent checkpoint
            (
                {
                    "configurable": {
                        "thread_id": "thread-1",
                        "checkpoint_ns": "ns1",
                        "checkpoint_id": "nonexistent",
                    }
                },
                None,
                None,
            ),
            # Latest checkpoint request
            (
                {"configurable": {"thread_id": "thread-1", "checkpoint_ns": "ns1"}},
                {
                    "checkpoint": create_checkpoint("chk-latest"),
                    "metadata": create_metadata(1),
                },
                True,
            ),
        ],
    )
    async def test_aget_tuple(
        self,
        async_redis_saver,
        fake_async_redis,
        config,
        checkpoint_data,
        expected_result,
    ):
        if checkpoint_data:
            await async_redis_saver.aput(
                config,
                checkpoint_data["checkpoint"],
                checkpoint_data["metadata"],
                {},
            )

        result = await async_redis_saver.aget_tuple(config)

        if expected_result is None:
            assert result is None
        else:
            assert result is not None
            assert result.checkpoint == checkpoint_data["checkpoint"]
            assert result.metadata == checkpoint_data["metadata"]

    @pytest.mark.parametrize(
        "thread_id, checkpoint_ns, checkpoint_id, writes_data, expected_count",
        [
            # No writes
            ("thread-1", "ns1", "chk-1", [], 0),
            # Single write
            ("thread-1", "ns1", "chk-1", [("task1", "channel1", "value1")], 1),
            # Multiple writes from same task
            (
                "thread-1",
                "ns1",
                "chk-1",
                [
                    ("task1", "channel1", "value1"),
                    ("task1", "channel2", "value2"),
                ],
                2,
            ),
            # Multiple writes from different tasks
            (
                "thread-1",
                "ns1",
                "chk-1",
                [
                    ("task1", "channel1", "value1"),
                    ("task2", "channel1", "value2"),
                ],
                2,
            ),
        ],
    )
    async def test_aload_pending_writes(
        self,
        async_redis_saver,
        fake_async_redis,
        thread_id,
        checkpoint_ns,
        checkpoint_id,
        writes_data,
        expected_count,
    ):
        # Store test writes
        for idx, (task_id, channel, value) in enumerate(writes_data):
            key = _make_redis_checkpoint_writes_key(
                thread_id,
                checkpoint_ns,
                checkpoint_id,
                task_id,
                idx,  # Use sequential index for each write
            )
            type_, serialized_value = async_redis_saver.serde.dumps_typed(value)
            await fake_async_redis.hset(
                key,
                mapping={
                    "channel": channel,
                    "type": type_,
                    "value": serialized_value,
                },
            )

        # Load and verify writes
        result = await async_redis_saver._aload_pending_writes(
            thread_id, checkpoint_ns, checkpoint_id
        )
        assert len(result) == expected_count

        if expected_count > 0:
            # Verify first write
            assert result[0][0] == writes_data[0][0]  # task_id
            assert result[0][1] == writes_data[0][1]  # channel
            assert result[0][2] == writes_data[0][2]  # value


class TestUtilityFunctions:
    @pytest.mark.parametrize(
        "thread_id, checkpoint_ns, checkpoint_id, expected_key",
        [
            # Basic case
            ("thread1", "ns1", "chk1", "checkpoint$thread1$ns1$chk1"),
            # Special characters
            ("thread-1", "ns/1", "chk.1", "checkpoint$thread-1$ns/1$chk.1"),
            # Long identifiers
            (
                "thread_very_long_123",
                "namespace_very_long_456",
                "checkpoint_very_long_789",
                "checkpoint$thread_very_long_123$namespace_very_long_456$checkpoint_very_long_789",
            ),
            # Empty namespace (should be filtered out)
            ("thread1", "", "chk1", "checkpoint$thread1$$chk1"),
            # Empty thread_id
            ("", "ns1", "chk1", "checkpoint$$ns1$chk1"),
            # Empty checkpoint_id
            ("thread1", "ns1", "", "checkpoint$thread1$ns1$"),
        ],
    )
    def test_make_redis_checkpoint_key(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        expected_key: str,
    ) -> None:
        """Test the _make_redis_checkpoint_key function with various inputs."""

        key = _make_redis_checkpoint_key(thread_id, checkpoint_ns, checkpoint_id)
        assert key == expected_key

    @pytest.mark.parametrize(
        "thread_id, checkpoint_ns, checkpoint_id, task_id, idx, expected_key",
        [
            # Basic case with index
            ("thread1", "ns1", "chk1", "task1", 0, "writes$thread1$ns1$chk1$task1$0"),
            # Case without index (None)
            ("thread1", "ns1", "chk1", "task1", None, "writes$thread1$ns1$chk1$task1"),
            # Special characters in identifiers
            (
                "thread-1",
                "ns/1",
                "chk.1",
                "task:1",
                0,
                "writes$thread-1$ns/1$chk.1$task:1$0",
            ),
            # Long identifiers
            (
                "thread_very_long_123",
                "namespace_very_long_456",
                "checkpoint_very_long_789",
                "task_very_long_012",
                1,
                "writes$thread_very_long_123$namespace_very_long_456$checkpoint_very_long_789$task_very_long_012$1",
            ),
            # Empty namespace
            ("thread1", "", "chk1", "task1", 0, "writes$thread1$$chk1$task1$0"),
            # Empty thread_id
            ("", "ns1", "chk1", "task1", 0, "writes$$ns1$chk1$task1$0"),
            # Negative index
            ("thread1", "ns1", "chk1", "task1", -1, "writes$thread1$ns1$chk1$task1$-1"),
            # Large index
            (
                "thread1",
                "ns1",
                "chk1",
                "task1",
                999999,
                "writes$thread1$ns1$chk1$task1$999999",
            ),
        ],
    )
    def test_make_redis_checkpoint_writes_key(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        task_id: str,
        idx: int | None,
        expected_key: str,
    ) -> None:
        """Test the _make_redis_checkpoint_writes_key function with various inputs."""
        key = _make_redis_checkpoint_writes_key(
            thread_id, checkpoint_ns, checkpoint_id, task_id, idx
        )
        assert key == expected_key

    @pytest.mark.parametrize(
        "key, expected_result, should_raise",
        [
            # Valid cases
            (
                "checkpoint$thread1$ns1$chk1",
                {
                    "thread_id": "thread1",
                    "checkpoint_ns": "ns1",
                    "checkpoint_id": "chk1",
                },
                False,
            ),
            # Special characters in identifiers
            (
                "checkpoint$thread-1$ns/1$chk.1",
                {
                    "thread_id": "thread-1",
                    "checkpoint_ns": "ns/1",
                    "checkpoint_id": "chk.1",
                },
                False,
            ),
            # Empty namespace
            (
                "checkpoint$thread1$$chk1",
                {
                    "thread_id": "thread1",
                    "checkpoint_ns": "",
                    "checkpoint_id": "chk1",
                },
                False,
            ),
            # Long identifiers
            (
                "checkpoint$thread_very_long_123$namespace_very_long_456$checkpoint_very_long_789",
                {
                    "thread_id": "thread_very_long_123",
                    "checkpoint_ns": "namespace_very_long_456",
                    "checkpoint_id": "checkpoint_very_long_789",
                },
                False,
            ),
            # UUID-like identifiers
            (
                "checkpoint$550e8400-e29b-41d4-a716-446655440000$ns1$chk1",
                {
                    "thread_id": "550e8400-e29b-41d4-a716-446655440000",
                    "checkpoint_ns": "ns1",
                    "checkpoint_id": "chk1",
                },
                False,
            ),
            # Invalid cases - wrong prefix
            ("invalid$thread1$ns1$chk1", None, True),
            # Invalid cases - wrong number of segments
            ("checkpoint$thread1$ns1", None, True),
            ("checkpoint$thread1$ns1$chk1$extra", None, True),
            # Invalid cases - empty segments
            (
                "checkpoint$$$",
                {
                    "thread_id": "",
                    "checkpoint_ns": "",
                    "checkpoint_id": "",
                },
                False,
            ),
            # Invalid cases - completely wrong format
            ("invalid_key", None, True),
            # Invalid cases - missing separator
            ("checkpointthread1ns1chk1", None, True),
        ],
    )
    def test_parse_redis_checkpoint_key(self, key, expected_result, should_raise):
        """Test _parse_redis_checkpoint_key with various inputs using table-driven tests.

        Args:
            key: Input Redis key to parse
            expected_result: Expected dictionary output for valid keys
            should_raise: Whether ValueError should be raised
        """
        if should_raise:
            with pytest.raises(ValueError):
                _parse_redis_checkpoint_key(key)
        else:
            result = _parse_redis_checkpoint_key(key)
            assert result == expected_result

    def test_parse_redis_checkpoint_writes_key(self):
        key = "writes$thread1$ns1$chk1$task1$0"
        result = _parse_redis_checkpoint_writes_key(key)
        assert result == {
            "thread_id": "thread1",
            "checkpoint_ns": "ns1",
            "checkpoint_id": "chk1",
            "task_id": "task1",
            "idx": "0",
        }

        with pytest.raises(ValueError):
            _parse_redis_checkpoint_writes_key("checkpoint$invalid$key")
