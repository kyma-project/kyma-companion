"""Incremental bookmark helpers. We store only a one-way hash of the session id
in HANA, never the raw id or any message text."""

import hashlib


def session_key(session_id: str) -> str:
    """SHA-256 hex digest of the session id — an opaque, non-reversible bookmark key."""
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def head_fingerprint(turns: list[dict]) -> str:
    """SHA-256 of the first turn's query — a stable per-conversation-instance identity.

    The first turn is append-only-stable within one conversation's life, so a
    mismatch means the session id was reused for a new conversation (e.g. after
    the old history expired). Empty string when there are no complete turns.
    """
    if not turns:
        return ""
    return hashlib.sha256(turns[0].get("query", "").encode("utf-8")).hexdigest()


def select_new_turns(turns: list[dict], already: int) -> list[dict]:
    """Return only turns past the watermark (turns are ordered by turn_index)."""
    return turns[already:]
