from collections import defaultdict
from datetime import UTC, datetime

import fakeredis
import pytest
import pytest_asyncio
from langgraph.checkpoint.base import Checkpoint
from langgraph.serde.jsonplus import JsonPlusSerializer

from utils.redis_checkpointer import RedisSaver


def create_checkpoint(checkpoint_id):
    return Checkpoint(
        v=1,
        id=checkpoint_id,
        ts=datetime.now(UTC).isoformat(),
        channel_values={},
        channel_versions={},
        versions_seen=defaultdict(dict),
        pending_sends=[],
    )


def create_metadata(step):
    return {"source": "input", "step": step, "writes": {}, "score": 1}


class TestRedisSaver:
    serde = JsonPlusSerializer()

    @pytest_asyncio.fixture
    async def fake_async_redis(self):
        async with fakeredis.FakeAsyncRedis() as client:
            yield client

    @pytest_asyncio.fixture(autouse=True)
    def setup(self, fake_async_redis):
        self.redis_saver = RedisSaver(async_connection=fake_async_redis)

    @pytest.mark.parametrize("config, checkpoint, metadata, expected_parent_ts", [
        (
                {"configurable": {"thread_id": "thread-1"}},
                "chk-1",
                create_metadata(1),
                ""
        ),
        (
                {"configurable": {"thread_id": "thread-1", "thread_ts": "chk-1"}},
                "chk-2",
                create_metadata(2),
                "chk-1"
        ),
    ])
    @pytest.mark.asyncio
    async def test_aput(self, config, checkpoint, metadata, expected_parent_ts, fake_async_redis):
        checkpoint_obj = create_checkpoint(checkpoint)
        await self.redis_saver.aput(config, checkpoint_obj, metadata)

        key = f"checkpoint:{config['configurable']['thread_id']}:{checkpoint}"
        actual_result = await fake_async_redis.hgetall(key)

        assert self.serde.loads(actual_result[b"checkpoint"].decode()) == checkpoint_obj
        assert self.serde.loads(actual_result[b"metadata"].decode()) == metadata
        assert actual_result[b"parent_ts"].decode() == expected_parent_ts

    @pytest.mark.parametrize("put_config, get_config, checkpoints, metadata, expected_checkpoint", [
        (
                {"configurable": {"thread_id": "thread-1"}},
                {"configurable": {"thread_id": "thread-1", "thread_ts": "chk-1"}},
                ["chk-1"],
                create_metadata(1),
                "chk-1"
        ),
        (
                {"configurable": {"thread_id": "thread-1", "thread_ts": "chk-1"}},
                {"configurable": {"thread_id": "thread-1", "thread_ts": "chk-2"}},
                ["chk-2"],
                create_metadata(2),
                "chk-2"
        ),
        (
                {"configurable": {"thread_id": "thread-1", "thread_ts": "chk-2"}},
                {"configurable": {"thread_id": "thread-1"}},
                ["chk-1", "chk-2", "chk-3"],
                create_metadata(3),
                "chk-3"
        ),
    ])
    @pytest.mark.asyncio
    async def test_aget(self, put_config, get_config, checkpoints, metadata, expected_checkpoint):
        for chk in checkpoints:
            await self.redis_saver.aput(put_config, create_checkpoint(chk), metadata)

        saved_data = await self.redis_saver.aget_tuple(get_config)

        assert saved_data.checkpoint["id"] == expected_checkpoint
        assert saved_data.metadata == metadata
        assert (saved_data.parent_config
                == (put_config if put_config["configurable"].get("thread_ts") else None))
