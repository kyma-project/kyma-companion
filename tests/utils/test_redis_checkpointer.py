from collections.abc import AsyncIterator

import fakeredis
import pytest
import pytest_asyncio
from langchain_core.runnables import RunnableConfig
from langgraph.channels.manager import create_checkpoint
from langgraph.checkpoint.base import (
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    empty_checkpoint,
)
from redis import asyncio as redis

from utils.redis_checkpointer import RedisSaver


class TestRedisSaver:
    @pytest_asyncio.fixture
    async def fake_async_redis(self) -> AsyncIterator[redis.Redis]:
        async with fakeredis.FakeAsyncRedis() as client:
            yield client

    @pytest_asyncio.fixture(autouse=True)
    def setup(self, fake_async_redis):
        self.redis_saver = RedisSaver(async_connection=fake_async_redis)

    config_1: RunnableConfig = {
        "configurable": {"thread_id": "thread-1"}
    }
    checkpoint_1: Checkpoint = empty_checkpoint()
    metadata_1: CheckpointMetadata = {
        "source": "input",
        "step": 2,
        "writes": {},
        "score": 1,
    }

    config_2: RunnableConfig = {
        "configurable": {"thread_id": "thread-2", "thread_ts": "2"}
    }
    checkpoint2: Checkpoint = create_checkpoint(checkpoint_1, {}, 1)
    metadata_2: CheckpointMetadata = {
        "source": "loop",
        "step": 1,
        "writes": {"foo": "bar"},
        "score": None,
    }

    @pytest.mark.parametrize("config,checkpoint,metadata,expected_result", [
        (config_1, checkpoint_1, metadata_1, CheckpointTuple(
            config=config_1,
            checkpoint=checkpoint_1,
            metadata=metadata_1,
            parent_config=None
        )),
        (config_2, checkpoint2, metadata_2, CheckpointTuple(
            config=config_2,
            checkpoint=checkpoint2,
            metadata=metadata_2,
            parent_config=config_2
        )
         ),
    ])
    @pytest.mark.asyncio
    async def test_get(self, config, checkpoint, metadata, expected_result):
        # save checkpoints
        thread_config = await self.redis_saver.aput(config, checkpoint, metadata)

        # Verify the data was saved in Redis
        saved_data = await self.redis_saver.aget_tuple(thread_config)

        # Verify the data was saved in Redis
        assert saved_data.checkpoint == expected_result.checkpoint
        assert saved_data.metadata == expected_result.metadata
        assert saved_data.parent_config == expected_result.parent_config
