"""Tests for Redis-backed LLM token usage store."""

import json
import time
from unittest.mock import patch

import fakeredis.aioredis
import pytest

from services.usage_store import (
    UsageStore,
    _extract_time_from_llm_usage_key,
    _get_llm_usage_key_filter,
    _get_llm_usage_key_prefix,
    _make_llm_usage_key,
    _safe_decode,
)


@pytest.fixture
def fake_redis():
    return fakeredis.aioredis.FakeRedis()


@pytest.fixture
def store(fake_redis):
    return UsageStore(conn=fake_redis)


class TestUsageStoreHelpers:
    """Tests for module-level helper functions."""

    def test_get_llm_usage_key_prefix(self):
        assert _get_llm_usage_key_prefix("cluster-1") == "llm_usage_cluster-1"

    def test_make_llm_usage_key_contains_prefix(self):
        key = _make_llm_usage_key("cluster-1")
        assert key.startswith("llm_usage_cluster-1_")

    def test_make_llm_usage_key_contains_timestamp(self):
        before = time.time()
        key = _make_llm_usage_key("cluster-1")
        after = time.time()
        ts = _extract_time_from_llm_usage_key(key)
        assert before <= ts <= after

    def test_get_llm_usage_key_filter(self):
        assert _get_llm_usage_key_filter("cluster-1") == "llm_usage_cluster-1_*"

    def test_extract_time_from_llm_usage_key(self):
        key = "llm_usage_cluster-1_1234567890.123"
        ts = _extract_time_from_llm_usage_key(key)
        assert ts == 1234567890.123

    @pytest.mark.parametrize(
        "input_val, expected",
        [
            (b"some_key", "some_key"),
            ("some_key", "some_key"),
        ],
    )
    def test_safe_decode(self, input_val, expected):
        assert _safe_decode(input_val) == expected


class TestUsageStoreWrite:
    """Tests for writing usage data."""

    @pytest.mark.asyncio
    async def test_write_returns_key(self, store):
        """Writing usage data returns the Redis key."""
        key = await store.awrite_llm_usage("cluster-1", {"tokens": 100})
        assert key.startswith("llm_usage_cluster-1_")

    @pytest.mark.asyncio
    async def test_write_without_ttl(self, store, fake_redis):
        """Writing without TTL stores data without expiration."""
        key = await store.awrite_llm_usage("cluster-1", {"tokens": 100})
        ttl = await fake_redis.ttl(key)
        # -1 means no expiration is set
        assert ttl == -1

    @pytest.mark.asyncio
    async def test_write_with_ttl(self, store, fake_redis):
        """Writing with TTL stores data with expiration."""
        key = await store.awrite_llm_usage("cluster-1", {"tokens": 100}, ttl=60)
        ttl = await fake_redis.ttl(key)
        assert 0 < ttl <= 60

    @pytest.mark.asyncio
    async def test_write_data_is_json(self, store, fake_redis):
        """Written data is valid JSON."""
        data = {"input_tokens": 50, "output_tokens": 30}
        key = await store.awrite_llm_usage("cluster-1", data)
        raw = await fake_redis.get(key)
        parsed = json.loads(raw)
        assert parsed == data


class TestUsageStoreList:
    """Tests for listing usage records."""

    @pytest.mark.asyncio
    async def test_list_empty(self, store):
        """Listing records for a cluster with no data returns empty list."""
        result = await store.alist_llm_usage_records("no-data", ttl=3600)
        assert result == []

    @pytest.mark.asyncio
    async def test_list_returns_recent_records(self, store):
        """Records written within the TTL window are returned."""
        data1 = {"tokens": 100}
        data2 = {"tokens": 200}
        await store.awrite_llm_usage("cluster-1", data1)
        await store.awrite_llm_usage("cluster-1", data2)
        records = await store.alist_llm_usage_records("cluster-1", ttl=3600)
        assert len(records) == 2
        assert data1 in records
        assert data2 in records

    @pytest.mark.asyncio
    async def test_list_excludes_expired_by_key_time(self, store, fake_redis):
        """Records whose key timestamp is older than TTL are excluded from listing."""
        # Write a record with an old timestamp in the key
        old_key = "llm_usage_cluster-1_1000000000.0"
        await fake_redis.set(old_key, json.dumps({"tokens": 50}))

        # Write a current record
        await store.awrite_llm_usage("cluster-1", {"tokens": 100})

        records = await store.alist_llm_usage_records("cluster-1", ttl=3600)
        # Only the recent record should be returned
        assert len(records) == 1
        assert records[0]["tokens"] == 100

    @pytest.mark.asyncio
    async def test_list_different_clusters_independent(self, store):
        """Records from different clusters do not interfere."""
        await store.awrite_llm_usage("cluster-a", {"tokens": 10})
        await store.awrite_llm_usage("cluster-b", {"tokens": 20})
        records_a = await store.alist_llm_usage_records("cluster-a", ttl=3600)
        records_b = await store.alist_llm_usage_records("cluster-b", ttl=3600)
        assert len(records_a) == 1
        assert records_a[0]["tokens"] == 10
        assert len(records_b) == 1
        assert records_b[0]["tokens"] == 20


class TestUsageStoreDeleteExpired:
    """Tests for deleting expired records."""

    @pytest.mark.asyncio
    async def test_delete_expired_removes_old_records(self, store, fake_redis):
        """Expired records (by key timestamp) are deleted."""
        # Insert an old record directly
        old_key = "llm_usage_cluster-1_1000000000.0"
        await fake_redis.set(old_key, json.dumps({"tokens": 50}))

        # Insert a current record
        await store.awrite_llm_usage("cluster-1", {"tokens": 100})

        await store.adelete_expired_llm_usage_records("cluster-1", ttl=3600)

        # Old record should be gone
        assert await fake_redis.get(old_key) is None

    @pytest.mark.asyncio
    async def test_delete_expired_keeps_recent_records(self, store, fake_redis):
        """Recent records are not deleted."""
        key = await store.awrite_llm_usage("cluster-1", {"tokens": 100})
        await store.adelete_expired_llm_usage_records("cluster-1", ttl=3600)
        assert await fake_redis.get(key) is not None

    @pytest.mark.asyncio
    async def test_delete_expired_no_records(self, store):
        """Deleting with no records does not raise an error."""
        await store.adelete_expired_llm_usage_records("no-data", ttl=3600)
