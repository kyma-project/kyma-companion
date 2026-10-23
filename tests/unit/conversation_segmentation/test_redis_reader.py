import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from conversation_segmentation.redis_reader import pair_turns, parse_messages, scan_conversations

pytestmark = pytest.mark.unit


def test_pair_turns_pairs_human_with_ai_finalizer_skipping_tool_steps():
    msgs = [
        {"type": "human", "content": "why is my pod crashing?"},
        {"type": "ai", "content": "", "tool_calls": [{"name": "fetch_pod_logs"}]},  # intermediate
        {"type": "ai", "content": "It is OOMKilled; raise the memory limit."},  # finalizer
    ]
    turns = pair_turns(msgs)
    assert turns == [
        {"turn_index": 0, "query": "why is my pod crashing?", "response": "It is OOMKilled; raise the memory limit."}
    ]


def test_pair_turns_drops_unfinished_turn():
    msgs = [{"type": "human", "content": "hello"}]  # no ai finalizer yet
    assert pair_turns(msgs) == []


def test_parse_messages_bad_json_returns_empty():
    assert parse_messages("{not json") == []


@pytest.mark.asyncio
async def test_scan_conversations_uses_scan_iter_and_strips_prefix():
    conn = MagicMock()

    async def _iter(match):
        for k in ["kyma_agent_conversation:s1", "kyma_agent_conversation:s2"]:
            yield k

    conn.scan_iter = _iter
    conn.get = AsyncMock(side_effect=[json.dumps([{"type": "human", "content": "hi"}]), None])
    out = await scan_conversations(conn, "kyma_agent_conversation:")
    assert out[0][0] == "s1" and json.loads(out[0][1])[0]["content"] == "hi"
    assert all(sid for sid, _ in out)  # s2 (None value) filtered out
