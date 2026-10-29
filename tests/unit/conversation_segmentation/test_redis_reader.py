import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from conversation_segmentation.redis_reader import iter_conversations, pair_turns, parse_messages

pytestmark = pytest.mark.unit


async def _collect(agen):
    return [item async for item in agen]


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


def test_pair_turns_extracts_text_from_list_content_blocks():
    """Content may be a list of typed blocks; only the text blocks are concatenated."""
    msgs = [
        {"type": "human", "content": [{"type": "text", "text": "why is "}, {"type": "text", "text": "mtls down?"}]},
        {"type": "ai", "content": [{"type": "text", "text": "check peer auth"}, {"type": "image", "url": "x"}]},
    ]
    turns = pair_turns(msgs)
    assert turns == [{"turn_index": 0, "query": "why is mtls down?", "response": "check peer auth"}]


@pytest.mark.asyncio
async def test_iter_conversations_uses_scan_iter_and_strips_prefix():
    conn = MagicMock()

    async def _iter(match):
        for k in ["kyma_agent_conversation:s1", "kyma_agent_conversation:s2"]:
            yield k

    conn.scan_iter = _iter
    conn.get = AsyncMock(side_effect=[json.dumps([{"type": "human", "content": "hi"}]), None])
    out = await _collect(iter_conversations(conn, "kyma_agent_conversation:"))
    assert out[0][0] == "s1" and json.loads(out[0][1])[0]["content"] == "hi"
    assert all(sid for sid, _ in out)  # s2 (None value) filtered out


@pytest.mark.asyncio
async def test_iter_conversations_sorts_and_limits_results():
    """A bounded run is reproducible even when Redis returns SCAN keys out of order."""
    conn = MagicMock()

    async def _iter(match):
        for key in ["kyma_agent_conversation:s3", "kyma_agent_conversation:s1", "kyma_agent_conversation:s2"]:
            yield key

    conn.scan_iter = _iter
    conn.get = AsyncMock(return_value="[]")

    out = await _collect(iter_conversations(conn, "kyma_agent_conversation:", max_conversations=2))

    assert [session_id for session_id, _ in out] == ["s1", "s2"]


@pytest.mark.asyncio
async def test_iter_conversations_deduplicates_scan_results_before_limiting():
    """Redis SCAN may return duplicates; each conversation must be fetched once."""
    conn = MagicMock()

    async def _iter(match):
        for key in [
            "kyma_agent_conversation:s2",
            "kyma_agent_conversation:s1",
            "kyma_agent_conversation:s1",
        ]:
            yield key

    conn.scan_iter = _iter
    conn.get = AsyncMock(return_value="[]")

    out = await _collect(iter_conversations(conn, "kyma_agent_conversation:", max_conversations=2))

    assert [session_id for session_id, _ in out] == ["s1", "s2"]
    assert [call.args[0] for call in conn.get.await_args_list] == [
        "kyma_agent_conversation:s1",
        "kyma_agent_conversation:s2",
    ]


@pytest.mark.asyncio
async def test_iter_conversations_fetches_one_transcript_at_a_time():
    """Only the lightweight key list is materialized; GET is deferred and per-id."""
    conn = MagicMock()
    fetched: list[str] = []

    async def _iter(match):
        for key in ["kyma_agent_conversation:s2", "kyma_agent_conversation:s1"]:
            yield key

    async def _get(key):
        fetched.append(key)
        return "[]"

    conn.scan_iter = _iter
    conn.get = _get

    agen = iter_conversations(conn, "kyma_agent_conversation:")
    first = await agen.__anext__()
    assert first[0] == "s1"
    assert fetched == ["kyma_agent_conversation:s1"]  # s2 not fetched until requested
    await _collect(agen)
    assert fetched == ["kyma_agent_conversation:s1", "kyma_agent_conversation:s2"]
