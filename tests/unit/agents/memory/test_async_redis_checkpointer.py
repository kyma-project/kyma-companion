import json

import fakeredis
import pytest
import pytest_asyncio

from agents.memory.async_redis_checkpointer import (
    AsyncRedisSaver,
    _get_llm_usage_key_prefix,
    _make_llm_usage_key,
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
