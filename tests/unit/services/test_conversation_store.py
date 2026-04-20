"""Tests for Redis-backed conversation message store."""

import fakeredis.aioredis
import pytest

from services.conversation_store import ConversationStore


@pytest.fixture
def fake_redis():
    return fakeredis.aioredis.FakeRedis()


@pytest.fixture
def store(fake_redis):
    return ConversationStore(conn=fake_redis, ttl=300)


class TestConversationStoreMessages:
    """Tests for message CRUD operations."""

    @pytest.mark.asyncio
    async def test_load_messages_empty(self, store):
        """Loading messages for a nonexistent conversation returns an empty list."""
        result = await store.load_messages("nonexistent-conv")
        assert result == []

    @pytest.mark.asyncio
    async def test_save_and_load_messages(self, store):
        """Saved messages can be loaded back."""
        conv_id = "conv-123"
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        await store.save_messages(conv_id, messages)
        loaded = await store.load_messages(conv_id)
        assert loaded == messages

    @pytest.mark.asyncio
    async def test_save_replaces_existing_messages(self, store):
        """Saving messages replaces the previous set entirely."""
        conv_id = "conv-replace"
        await store.save_messages(conv_id, [{"role": "user", "content": "first"}])
        await store.save_messages(conv_id, [{"role": "user", "content": "second"}])
        loaded = await store.load_messages(conv_id)
        assert len(loaded) == 1
        assert loaded[0]["content"] == "second"

    @pytest.mark.asyncio
    async def test_save_empty_messages(self, store):
        """Saving an empty list stores an empty array."""
        conv_id = "conv-empty"
        await store.save_messages(conv_id, [])
        loaded = await store.load_messages(conv_id)
        assert loaded == []

    @pytest.mark.asyncio
    async def test_different_conversations_independent(self, store):
        """Messages from different conversations do not interfere."""
        await store.save_messages("conv-a", [{"role": "user", "content": "A"}])
        await store.save_messages("conv-b", [{"role": "user", "content": "B"}])
        assert (await store.load_messages("conv-a"))[0]["content"] == "A"
        assert (await store.load_messages("conv-b"))[0]["content"] == "B"


class TestConversationStoreTTL:
    """Tests for TTL behaviour on messages."""

    @pytest.mark.asyncio
    async def test_messages_key_has_ttl(self, fake_redis, store):
        """Saved messages should have a TTL set."""
        conv_id = "conv-ttl"
        await store.save_messages(conv_id, [{"role": "user", "content": "test"}])
        key = store._messages_key(conv_id)
        ttl = await fake_redis.ttl(key)
        assert ttl > 0
        assert ttl <= 300

    @pytest.mark.asyncio
    async def test_owner_key_has_ttl(self, fake_redis, store):
        """Setting a thread owner should set a TTL on the owner key."""
        conv_id = "conv-owner-ttl"
        await store.set_thread_owner(conv_id, "user-1")
        key = store._owner_key(conv_id)
        ttl = await fake_redis.ttl(key)
        assert ttl > 0
        assert ttl <= 300


class TestConversationStoreThreadOwnership:
    """Tests for thread ownership operations."""

    @pytest.mark.asyncio
    async def test_get_thread_owner_not_set(self, store):
        """Getting owner for a conversation with no owner returns None."""
        result = await store.get_thread_owner("conv-no-owner")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get_thread_owner(self, store):
        """Setting and getting the thread owner works correctly."""
        conv_id = "conv-owned"
        await store.set_thread_owner(conv_id, "user-abc")
        owner = await store.get_thread_owner(conv_id)
        assert owner == "user-abc"

    @pytest.mark.asyncio
    async def test_set_thread_owner_overwrites(self, store):
        """Setting the thread owner overwrites the previous owner."""
        conv_id = "conv-overwrite"
        await store.set_thread_owner(conv_id, "user-1")
        await store.set_thread_owner(conv_id, "user-2")
        owner = await store.get_thread_owner(conv_id)
        assert owner == "user-2"

    @pytest.mark.asyncio
    async def test_owner_independent_of_messages(self, store):
        """Thread owner and messages are stored independently."""
        conv_id = "conv-independent"
        await store.set_thread_owner(conv_id, "owner-1")
        await store.save_messages(conv_id, [{"role": "user", "content": "msg"}])
        # Both should be retrievable
        assert await store.get_thread_owner(conv_id) == "owner-1"
        assert len(await store.load_messages(conv_id)) == 1


class TestConversationStoreKeyFormat:
    """Tests for internal key format."""

    def test_messages_key_format(self, store):
        assert store._messages_key("abc-123") == "conv:abc-123:messages"

    def test_owner_key_format(self, store):
        assert store._owner_key("abc-123") == "conv:abc-123:owner"
