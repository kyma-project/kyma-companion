"""Read Companion conversations from Redis and pair them into (query, response) turns.

Values are single JSON-string keys `kyma_agent_conversation:{session_id}` holding a
list of serialized messages (keys: type, content, tool_calls). We SCAN (never KEYS)
so we don't block Redis. Pairing mirrors the PoC: a ReAct turn is
human -> ai(tool_calls)* -> ai(final answer); we pair the human with the finalizer.
"""

import json
import logging

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


async def scan_conversations(conn: Redis, prefix: str) -> list[tuple[str, str]]:
    """SCAN all `{prefix}*` keys; return (session_id, raw_json), skipping evicted keys."""
    results: list[tuple[str, str]] = []
    async for key in conn.scan_iter(match=f"{prefix}*"):
        key_str = key.decode() if isinstance(key, bytes) else key
        raw = await conn.get(key_str)
        if raw is None:
            continue  # evicted between SCAN and GET
        raw_str = raw.decode() if isinstance(raw, bytes) else raw
        results.append((key_str[len(prefix) :], raw_str))
    return results
