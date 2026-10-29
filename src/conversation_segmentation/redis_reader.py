"""Read Companion conversations from Redis and pair them into (query, response) turns.

Values are single JSON-string keys `kyma_agent_conversation:{session_id}` holding a
list of serialized messages (keys: type, content, tool_calls). We SCAN (never KEYS)
so we don't block Redis. Pairing mirrors the PoC: a ReAct turn is
human -> ai(tool_calls)* -> ai(final answer); we pair the human with the finalizer.
"""

import json
import logging
from collections.abc import AsyncIterator

from redis.asyncio import Redis

log = logging.getLogger(__name__)


def _extract_text(content: str | list | None) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(b["text"] for b in content if isinstance(b, dict) and b.get("type") == "text" and "text" in b)
    return ""


def parse_messages(raw_json: str) -> list[dict]:
    """Parse the stored JSON message array; [] on malformed input."""
    try:
        msgs = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        log.warning("Malformed conversation JSON; skipping")
        return []
    return msgs if isinstance(msgs, list) else []


def pair_turns(msgs: list[dict]) -> list[dict]:
    """Pair each human message with its ai finalizer (the ai message with no tool_calls)."""
    turns: list[dict] = []
    pending_human: dict | None = None
    for msg in msgs:
        if not isinstance(msg, dict):
            continue
        mtype = msg.get("type", "")
        if mtype == "human":
            pending_human = msg
        elif mtype == "ai" and pending_human is not None:
            if msg.get("tool_calls"):
                continue  # intermediate ReAct step; await finalizer
            turns.append(
                {
                    "turn_index": len(turns),
                    "query": _extract_text(pending_human.get("content", "")),
                    "response": _extract_text(msg.get("content", "")),
                }
            )
            pending_human = None
    return turns


async def iter_conversations(conn: Redis, prefix: str, max_conversations: int = 0) -> AsyncIterator[tuple[str, str]]:
    """Yield ``(session_id, raw_json)`` in deterministic session-id order, one at a time.

    Only the lightweight set of session ids is held in memory; each (potentially
    large) transcript is fetched and yielded individually, so memory stays bounded
    regardless of corpus size. Redis SCAN gives no ordering, so the ids are sorted
    before fetching to keep a bounded or resumed run reproducible. A non-positive
    limit means all matching conversations.
    """
    session_ids: set[str] = set()
    async for key in conn.scan_iter(match=f"{prefix}*"):
        key_str = key.decode() if isinstance(key, bytes) else key
        session_ids.add(key_str[len(prefix) :])
    selected_session_ids = sorted(session_ids)
    if max_conversations > 0:
        selected_session_ids = selected_session_ids[:max_conversations]
    for session_id in selected_session_ids:
        raw = await conn.get(f"{prefix}{session_id}")
        if raw is None:
            continue  # evicted between SCAN and GET
        yield session_id, raw.decode() if isinstance(raw, bytes) else raw
