import asyncio
import json
import time
from collections import defaultdict
from datetime import UTC, datetime

import fakeredis
import pytest
import pytest_asyncio
from langgraph.checkpoint.base import Checkpoint
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from agents.memory.async_redis_checkpointer import (
    AsyncRedisSaver,
    _extract_time_from_llm_usage_key,
    _get_llm_usage_key_filter,
    _get_llm_usage_key_prefix,
    _make_llm_usage_key,
    _make_redis_checkpoint_key,
    _make_redis_checkpoint_writes_key,
    _parse_redis_checkpoint_key,
    _parse_redis_checkpoint_writes_key,
    _safe_decode,
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
        "config, checkpoint_data, ttl",
        [
            # Test Case 5 Sec ttl
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
                5,
            ),
            # Test Case 10 Sec ttl
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
                10,
            ),
        ],
    )
    async def test_aput_redis_ttl(
        self,
        async_redis_saver,
        fake_async_redis,
        config,
        checkpoint_data,
        ttl,
    ):

        await async_redis_saver.aput(
            config,
            checkpoint_data["checkpoint"],
            checkpoint_data["metadata"],
            {},
            redis_ttl=ttl,
        )

        result = await async_redis_saver.aget_tuple(config)

        # Check if the data is stored
        assert result is not None

        # Wait for the TTL to expire
        await asyncio.sleep(ttl + 2)  # Adding 2 second to ensure TTL has expired

        # Check if the data is deleted after TTL
        stored_data_after_ttl = await async_redis_saver.aget_tuple(config)
        assert not stored_data_after_ttl, "Data should be deleted after TTL"

    @pytest.mark.parametrize(
        "config, writes, task_id, expected_data, ttl",
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
                5,
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
                {"channel": "channel1", "value": "value1"},
                10,  # Check first write
            ),
        ],
    )
    async def test_redis_ttl_for_writes(
        self,
        async_redis_saver,
        fake_async_redis,
        config,
        writes,
        task_id,
        expected_data,
        ttl,
    ):
        # Store the data in Redis with a TTL
        await async_redis_saver.aput_writes(config, writes, task_id, redis_ttl=ttl)

        # Generate the Redis key
        key = _make_redis_checkpoint_writes_key(
            config["configurable"]["thread_id"],
            config["configurable"]["checkpoint_ns"],
            config["configurable"]["checkpoint_id"],
            task_id,
            0,
        )

        # Check if the data is stored correctly
        stored_data = await fake_async_redis.hgetall(key)
        assert stored_data[b"channel"] == expected_data["channel"].encode()
        assert (
            stored_data[b"value"]
            == async_redis_saver.serde.dumps_typed(expected_data["value"])[1]
        )

        # Wait for the TTL to expire
        await asyncio.sleep(ttl + 2)  # Adding 2 second to ensure TTL has expired

        # Check if the data is deleted after TTL
        stored_data_after_ttl = await fake_async_redis.hgetall(key)
        assert not stored_data_after_ttl, "Data should be deleted after TTL"

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

    async def test_aget_tuple_backward_compatibility_legacy_metadata(
        self, async_redis_saver, fake_async_redis
    ):
        """Test that checkpoints with legacy JSON metadata (without metadata_type) can still be read."""
        # Setup: Create a checkpoint in the old format (without metadata_type field)
        config = {
            "configurable": {
                "thread_id": "thread-legacy",
                "checkpoint_ns": "ns1",
                "checkpoint_id": "chk-legacy",
            }
        }
        checkpoint = create_checkpoint("chk-legacy")
        metadata = create_metadata(1)

        # Manually store checkpoint data in the old format (using JSON for metadata)
        key = _make_redis_checkpoint_key("thread-legacy", "ns1", "chk-legacy")
        type_, serialized_checkpoint = async_redis_saver.serde.dumps_typed(checkpoint)
        # Old format: metadata stored as JSON bytes (no metadata_type field)
        serialized_metadata = json.dumps(metadata).encode()
        data = {
            "checkpoint": serialized_checkpoint,
            "type": type_,
            "checkpoint_id": "chk-legacy",
            "metadata": serialized_metadata,
            # Note: no metadata_type field (legacy format)
            "parent_checkpoint_id": "",
        }
        await fake_async_redis.hset(key, mapping=data)

        # Test: Retrieve the checkpoint and verify backward compatibility
        result = await async_redis_saver.aget_tuple(config)

        # Verify: Should successfully read legacy checkpoint
        assert result is not None
        assert result.checkpoint == checkpoint
        assert result.metadata == metadata

    async def test_alist_backward_compatibility_legacy_metadata(
        self, async_redis_saver, fake_async_redis
    ):
        """Test that alist can handle checkpoints with legacy JSON metadata (without metadata_type)."""
        # Setup: Create two checkpoints - one new format, one legacy format
        thread_id = "thread-alist-legacy"
        checkpoint_ns = "ns1"

        # New format checkpoint
        config_new = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": "chk-new",
            }
        }
        checkpoint_new = create_checkpoint("chk-new")
        metadata_new = create_metadata(1)
        await async_redis_saver.aput(config_new, checkpoint_new, metadata_new, {})

        # Legacy format checkpoint
        checkpoint_legacy = create_checkpoint("chk-legacy")
        metadata_legacy = create_metadata(2)
        key_legacy = _make_redis_checkpoint_key(thread_id, checkpoint_ns, "chk-legacy")
        type_, serialized_checkpoint = async_redis_saver.serde.dumps_typed(
            checkpoint_legacy
        )
        serialized_metadata = json.dumps(metadata_legacy).encode()
        data = {
            "checkpoint": serialized_checkpoint,
            "type": type_,
            "checkpoint_id": "chk-legacy",
            "metadata": serialized_metadata,
            # Note: no metadata_type field (legacy format)
            "parent_checkpoint_id": "",
        }
        await fake_async_redis.hset(key_legacy, mapping=data)

        # Test: List all checkpoints
        config_list = {
            "configurable": {"thread_id": thread_id, "checkpoint_ns": checkpoint_ns}
        }
        results = [result async for result in async_redis_saver.alist(config_list)]

        # Verify: Both checkpoints should be retrieved correctly
        expected_checkpoint_count = 2
        assert len(results) == expected_checkpoint_count
        checkpoint_ids = {r.checkpoint["id"] for r in results}
        assert "chk-new" in checkpoint_ids
        assert "chk-legacy" in checkpoint_ids

        # Verify metadata for both
        for result in results:
            if result.checkpoint["id"] == "chk-new":
                assert result.metadata == metadata_new
            elif result.checkpoint["id"] == "chk-legacy":
                assert result.metadata == metadata_legacy

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

    @pytest.mark.parametrize(
        "cluster_id, data, ttl",
        [
            ("cluster1", {"usage": 100}, 0),
            ("test-cluster", {"usage": 200}, 10),
            ("123", {"usage": 300}, 5),
        ],
    )
    async def test_awrite_llm_usage(
        self, async_redis_saver, fake_async_redis, cluster_id, data, ttl
    ):
        # when
        key = await async_redis_saver.awrite_llm_usage(cluster_id, data, ttl)

        # then
        stored_data = await fake_async_redis.get(key)
        assert stored_data is not None
        assert json.loads(stored_data) == data

        if ttl > 0:
            ttl_value = await fake_async_redis.ttl(key)
            assert ttl_value > 0

    async def test_adelete_expired_llm_usage_records(
        self, async_redis_saver, fake_async_redis
    ):
        # given
        num_of_records = 3
        cluster_id = f"cluster_usage_record_deletion_test1_{time.time()}"
        # Set up the keys in Redis
        sample_data = {"usage": 100}
        # insert 3 records.
        ttl = 2
        for _ in range(num_of_records):
            await async_redis_saver.awrite_llm_usage(cluster_id, sample_data)

        # simulate waiting for the TTL.
        await asyncio.sleep(2)  # Adding 2 second to ensure TTL has expired

        # insert 3 more records.
        for _ in range(num_of_records):
            await async_redis_saver.awrite_llm_usage(cluster_id, sample_data)

        all_keys = await fake_async_redis.keys(_get_llm_usage_key_filter(cluster_id))
        assert len(all_keys) == 2 * num_of_records

        # when
        # Call the method to delete expired records
        await async_redis_saver.adelete_expired_llm_usage_records(cluster_id, ttl)

        # then
        # Check the remaining keys in Redis
        remaining_keys = await fake_async_redis.keys(
            _get_llm_usage_key_filter(cluster_id)
        )
        assert len(remaining_keys) == num_of_records
        for key in remaining_keys:
            assert (
                _extract_time_from_llm_usage_key(_safe_decode(key)) > time.time() - ttl
            )

    async def test_alist_llm_usage_records(self, async_redis_saver, fake_async_redis):
        # given
        num_of_records = 3
        cluster_id1 = f"cluster_list_llm_usage_records_test1_{time.time()}"
        cluster_id2 = f"cluster_list_llm_usage_records_test2_{time.time()}"
        # Set up the keys in Redis
        # insert 3 records with different cluster_id (as noise).
        ttl = 3
        for _ in range(num_of_records):
            await async_redis_saver.awrite_llm_usage(
                cluster_id2, {"epoch": time.time()}
            )

        # insert 3 records.
        for _ in range(num_of_records):
            await async_redis_saver.awrite_llm_usage(
                cluster_id1, {"epoch": time.time()}
            )

        # simulate waiting for the TTL.
        await asyncio.sleep(ttl + 2)  # Adding 2 second to ensure TTL has expired

        # insert 3 records with large ttl.
        for _ in range(num_of_records):
            await async_redis_saver.awrite_llm_usage(
                cluster_id1, {"epoch": time.time()}
            )

        # when
        records = await async_redis_saver.alist_llm_usage_records(cluster_id1, ttl)

        # then
        assert len(records) == num_of_records

        all_keys = await fake_async_redis.keys(_get_llm_usage_key_filter(cluster_id1))
        assert len(all_keys) == 2 * num_of_records

        for record in records:
            assert record["epoch"] > time.time() - ttl


class TestUtilityFunctions:
    def test_make_redis_checkpoint_key(self):
        key = _make_redis_checkpoint_key("thread1", "ns1", "chk1")
        assert key == "checkpoint$thread1$ns1$chk1"

    def test_make_redis_checkpoint_writes_key(self):
        key = _make_redis_checkpoint_writes_key("thread1", "ns1", "chk1", "task1", 0)
        assert key == "writes$thread1$ns1$chk1$task1$0"

        key_no_idx = _make_redis_checkpoint_writes_key(
            "thread1", "ns1", "chk1", "task1", None
        )
        assert key_no_idx == "writes$thread1$ns1$chk1$task1"

    def test_parse_redis_checkpoint_key(self):
        key = "checkpoint$thread1$ns1$chk1"
        result = _parse_redis_checkpoint_key(key)
        assert result == {
            "thread_id": "thread1",
            "checkpoint_ns": "ns1",
            "checkpoint_id": "chk1",
        }

        with pytest.raises(ValueError):
            _parse_redis_checkpoint_key("invalid$key")

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

    @pytest.mark.parametrize(
        "cluster_id, expected_prefix",
        [
            ("cluster1", "llm_usage_cluster1"),
            ("test-cluster", "llm_usage_test-cluster"),
            ("123", "llm_usage_123"),
        ],
    )
    def test_get_llm_usage_key_prefix(self, cluster_id, expected_prefix):
        assert _get_llm_usage_key_prefix(cluster_id) == expected_prefix

    @pytest.mark.parametrize(
        "cluster_id",
        [
            "cluster1",
            "test-cluster",
            "123",
        ],
    )
    def test_make_llm_usage_key(self, cluster_id):
        # when
        key = _make_llm_usage_key(cluster_id)

        # then
        assert key.startswith(_get_llm_usage_key_prefix(cluster_id))
        parts = key.split("_")
        expected_parts_count = 4
        assert len(parts) == expected_parts_count  # prefix, cluster_id, timestamp
        # check that the last part is a float.
        assert float(parts[-1]) > 0

    @pytest.mark.parametrize(
        "cluster_id, expected_filter",
        [
            ("cluster1", "llm_usage_cluster1_*"),
            ("test-cluster", "llm_usage_test-cluster_*"),
            ("123", "llm_usage_123_*"),
        ],
    )
    def test_get_llm_usage_key_filter(self, cluster_id, expected_filter):
        assert _get_llm_usage_key_filter(cluster_id) == expected_filter

    @pytest.mark.parametrize(
        "key, expected_time",
        [
            ("llm_usage_cluster1_1633036800.123456", 1633036800.123456),
            ("llm_usage_test-cluster_1633036800.654321", 1633036800.654321),
            ("llm_usage_123_1633036800.789012", 1633036800.789012),
        ],
    )
    def test_extract_time_from_llm_usage_key(self, key, expected_time):
        assert _extract_time_from_llm_usage_key(key) == expected_time
