import asyncio
import json
import time

import fakeredis
import pytest
import pytest_asyncio

from agents.memory.async_redis_checkpointer import (
    AsyncRedisSaver,
    _extract_time_from_llm_usage_key,
    _get_llm_usage_key_filter,
    _get_llm_usage_key_prefix,
    _make_llm_usage_key,
    _safe_decode,
)


@pytest.mark.asyncio
class TestAsyncRedisSaver:
    @pytest_asyncio.fixture
    async def fake_async_redis(self):
        async with fakeredis.FakeAsyncRedis() as client:
            yield client

    @pytest_asyncio.fixture
    def async_redis_saver(self, fake_async_redis):
        return AsyncRedisSaver(conn=fake_async_redis)

    @pytest.mark.parametrize(
        "cluster_id, data, ttl",
        [
            ("cluster1", {"usage": 100}, 0),
            ("test-cluster", {"usage": 200}, 10),
            ("123", {"usage": 300}, 5),
        ],
    )
    async def test_awrite_llm_usage(self, async_redis_saver, fake_async_redis, cluster_id, data, ttl):
        key = await async_redis_saver.awrite_llm_usage(cluster_id, data, ttl)

        stored_data = await fake_async_redis.get(key)
        assert stored_data is not None
        assert json.loads(stored_data) == data

        if ttl > 0:
            ttl_value = await fake_async_redis.ttl(key)
            assert ttl_value > 0

    async def test_adelete_expired_llm_usage_records(self, async_redis_saver, fake_async_redis):
        num_of_records = 3
        cluster_id = f"cluster_usage_record_deletion_test1_{time.time()}"
        sample_data = {"usage": 100}
        ttl = 2
        for _ in range(num_of_records):
            await async_redis_saver.awrite_llm_usage(cluster_id, sample_data)

        await asyncio.sleep(2)

        for _ in range(num_of_records):
            await async_redis_saver.awrite_llm_usage(cluster_id, sample_data)

        all_keys = await fake_async_redis.keys(_get_llm_usage_key_filter(cluster_id))
        assert len(all_keys) == 2 * num_of_records

        await async_redis_saver.adelete_expired_llm_usage_records(cluster_id, ttl)

        remaining_keys = await fake_async_redis.keys(_get_llm_usage_key_filter(cluster_id))
        assert len(remaining_keys) == num_of_records
        for key in remaining_keys:
            assert _extract_time_from_llm_usage_key(_safe_decode(key)) > time.time() - ttl

    async def test_alist_llm_usage_records(self, async_redis_saver, fake_async_redis):
        num_of_records = 3
        cluster_id1 = f"cluster_list_llm_usage_records_test1_{time.time()}"
        cluster_id2 = f"cluster_list_llm_usage_records_test2_{time.time()}"
        ttl = 3
        for _ in range(num_of_records):
            await async_redis_saver.awrite_llm_usage(cluster_id2, {"epoch": time.time()})

        for _ in range(num_of_records):
            await async_redis_saver.awrite_llm_usage(cluster_id1, {"epoch": time.time()})

        await asyncio.sleep(ttl + 2)

        for _ in range(num_of_records):
            await async_redis_saver.awrite_llm_usage(cluster_id1, {"epoch": time.time()})

        records = await async_redis_saver.alist_llm_usage_records(cluster_id1, ttl)

        assert len(records) == num_of_records

        all_keys = await fake_async_redis.keys(_get_llm_usage_key_filter(cluster_id1))
        assert len(all_keys) == 2 * num_of_records

        for record in records:
            assert record["epoch"] > time.time() - ttl


class TestUtilityFunctions:
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
        key = _make_llm_usage_key(cluster_id)

        assert key.startswith(_get_llm_usage_key_prefix(cluster_id))
        parts = key.split("_")
        expected_parts_count = 4
        assert len(parts) == expected_parts_count
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
