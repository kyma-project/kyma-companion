"""Incremental bookmark helpers. We store only a one-way hash of the session id
in HANA, never the raw id or any message text."""

import hashlib


def session_key(session_id: str) -> str:
    """SHA-256 hex digest of the session id — an opaque, non-reversible bookmark key."""
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()


def conversation_instance_key(session_id: str, head_fingerprint: str) -> str:
    """Hash one conversation instance, keeping reused session IDs historically distinct."""
    return hashlib.sha256(f"{session_id}\0{head_fingerprint}".encode()).hexdigest()


def head_fingerprint(turns: list[dict], conversation_id: str = "") -> str:
    """Return the stable opaque instance ID, falling back to the legacy query hash.

    New Redis records receive a random 64-hex ID when first saved. That ID changes when
    an expired session key is recreated, even if its first query repeats. Legacy message
    arrays retain the former first-query fingerprint until their next application write.
    """
    if conversation_id:
        return conversation_id
    if not turns:
        return ""
    return hashlib.sha256(turns[0].get("query", "").encode("utf-8")).hexdigest()


def select_new_turns(turns: list[dict], already: int) -> list[dict]:
    """Return only turns past the watermark (turns are ordered by turn_index)."""
    return turns[already:]
