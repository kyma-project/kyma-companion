"""Unit tests for services/encryption_cache.py."""

from unittest.mock import patch

import fakeredis
import pytest
import pytest_asyncio

from services.encryption_cache import (
    _ENCRYPTION_CACHE_KEY_PREFIX,
    _NONCE_KEY_PREFIX,
    EncryptionCache,
    IEncryptionCache,
    get_encryption_cache,
)
from utils.settings import NONCE_REPLAY_WINDOW_SECONDS, REDIS_TTL

_SESSION_ID = "test-session-id"
_NONCE = "test-nonce"
_PUBLIC_KEY = "test-public-key"
_FIXED_TIME = 1_000_000.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockRedisService:
    """Minimal IRedisService backed by FakeAsyncRedis for testing."""

    def __init__(self, connection: fakeredis.FakeAsyncRedis) -> None:
        self._connection = connection

    def get_connection(self) -> fakeredis.FakeAsyncRedis:
        return self._connection


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEncryptionCache:
    @pytest_asyncio.fixture
    async def fake_redis(self) -> fakeredis.FakeAsyncRedis:
        async with fakeredis.FakeAsyncRedis(decode_responses=True) as client:
            yield client

    @pytest.fixture
    def cache(self, fake_redis: fakeredis.FakeAsyncRedis) -> EncryptionCache:
        return EncryptionCache(redis=MockRedisService(fake_redis))

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_case, session_id, public_key",
        [
            pytest.param(
                "stores the public key at the correct Redis key with the configured TTL",
                "session-abc",
                "public-key-abc",
                id="session_abc",
            ),
            pytest.param(
                "uses a separate Redis key for a different session ID",
                "session-xyz",
                "public-key-xyz",
                id="session_xyz",
            ),
        ],
    )
    async def test_save_client_public_key(
        self,
        fake_redis: fakeredis.FakeAsyncRedis,
        cache: EncryptionCache,
        test_case: str,
        session_id: str,
        public_key: str,
    ):
        # When:
        await cache.save_client_public_key(session_id, public_key)

        # Then:
        stored = await fake_redis.get(f"{_ENCRYPTION_CACHE_KEY_PREFIX}{session_id}")
        assert stored == public_key, test_case
        ttl = await fake_redis.ttl(f"{_ENCRYPTION_CACHE_KEY_PREFIX}{session_id}")
        assert ttl == REDIS_TTL, test_case

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_case, stored_value, expected_result",
        [
            pytest.param(
                "returns the public key string when it exists in Redis",
                _PUBLIC_KEY,
                _PUBLIC_KEY,
                id="key_exists",
            ),
            pytest.param(
                "returns None when the session key is absent from Redis",
                None,
                None,
                id="key_absent",
            ),
        ],
    )
    async def test_get_client_public_key(
        self,
        fake_redis: fakeredis.FakeAsyncRedis,
        cache: EncryptionCache,
        test_case: str,
        stored_value: str | None,
        expected_result: str | None,
    ):
        # Given:
        if stored_value is not None:
            await fake_redis.set(f"{_ENCRYPTION_CACHE_KEY_PREFIX}{_SESSION_ID}", stored_value)

        # When:
        result = await cache.get_client_public_key(_SESSION_ID)

        # Then:
        assert result == expected_result, test_case

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_case, stored_first_seen_offset, expected_result",
        [
            pytest.param(
                "returns True and stores the nonce timestamp on first use",
                None,
                True,
                id="first_use",
            ),
            pytest.param(
                "returns True when the nonce was first seen within the replay window",
                -(NONCE_REPLAY_WINDOW_SECONDS - 10),
                True,
                id="within_window",
            ),
            pytest.param(
                "returns False when the nonce was first seen outside the replay window",
                -(NONCE_REPLAY_WINDOW_SECONDS + 10),
                False,
                id="outside_window",
            ),
        ],
    )
    async def test_is_nonce_allowed(
        self,
        fake_redis: fakeredis.FakeAsyncRedis,
        cache: EncryptionCache,
        test_case: str,
        stored_first_seen_offset: float | None,
        expected_result: bool,
    ):
        # Given:
        nonce_key = f"{_NONCE_KEY_PREFIX}{_SESSION_ID}:{_NONCE}"
        if stored_first_seen_offset is not None:
            first_seen = _FIXED_TIME + stored_first_seen_offset
            await fake_redis.set(nonce_key, str(first_seen))

        # When:
        with patch("services.encryption_cache.time") as mock_time:
            mock_time.time.return_value = _FIXED_TIME
            result = await cache.is_nonce_allowed(_SESSION_ID, _NONCE)

        # Then:
        assert result == expected_result, test_case

        # For first use: verify the nonce was persisted with the correct timestamp.
        if stored_first_seen_offset is None:
            stored = await fake_redis.get(nonce_key)
            assert stored == str(_FIXED_TIME), test_case

    def test_encryption_cache_implements_iencryption_cache(self, fake_redis: fakeredis.FakeAsyncRedis):
        """EncryptionCache must satisfy the IEncryptionCache Protocol."""
        cache = EncryptionCache(redis=MockRedisService(fake_redis))
        assert isinstance(cache, IEncryptionCache)

    @pytest.mark.parametrize(
        "test_case",
        [
            pytest.param(
                "returns an EncryptionCache instance wrapping the provided Redis service",
                id="returns_encryption_cache",
            ),
        ],
    )
    def test_get_encryption_cache(
        self,
        fake_redis: fakeredis.FakeAsyncRedis,
        test_case: str,
    ):
        # Given:
        redis_service = MockRedisService(fake_redis)

        # When:
        cache = get_encryption_cache(redis=redis_service)

        # Then:
        assert isinstance(cache, EncryptionCache), test_case
        assert isinstance(cache, IEncryptionCache), test_case
        assert cache._redis is redis_service, test_case
