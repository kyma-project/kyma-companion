"""Canonicalization: turn a model's per-turn proposal into a stable, groupable
``topic_key`` and a best-effort-scrubbed example summary.

The ``topic_key`` is ``area/intent/capability-slug``. It is the aggregation key:
two conversations that produce the same key count as two conversations on one topic,
even if the user's wording differed. The capability is only slugified — never folded
through a synonym map — so the topic table grows organically from the data. The
free-text ``topic`` label and ``summary`` are kept only for human insight and never
contribute to the key.

Nothing here persists raw conversation text. Every stored free-text field (``capability``,
``label``, ``summary``) is passed through ``_scrub_identifiers`` to strip obvious
identifiers (IPs, URLs, UUIDs, emails, long tokens, namespace/resource paths) as
defense-in-depth on top of the prompt instruction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256

from conversation_segmentation.taxonomy import (
    GENERAL_CAPABILITY,
    Area,
    Intent,
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Patterns scrubbed from example summaries before anything is stored.
_SCRUB_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"https?://\S+"), "<url>"),
    (re.compile(r"\b[\w.-]+@[\w.-]+\.\w+\b"), "<email>"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b"), "<ip>"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "<uuid>"),
    (re.compile(r"\b[A-Za-z0-9+/]{32,}={0,2}\b"), "<token>"),
    (re.compile(r"\b(?:namespace|ns)[=:/]\s*\S+", re.I), "<namespace>"),
]

_MAX_SUMMARY_LEN = 200
MAX_CAPABILITY_LEN = 128
MAX_TOPIC_KEY_LEN = 256
_HASH_SUFFIX_LEN = 16


def slugify(text: str) -> str:
    """Lowercase and collapse non-alphanumerics to single hyphens; '' when empty."""
    return _NON_ALNUM.sub("-", text.strip().lower()).strip("-")


def _scrub_identifiers(text: str) -> str:
    """Replace identifier-like substrings (IPs, URLs, UUIDs, emails, tokens, namespaces)
    with placeholders and collapse whitespace. Shared by every stored free-text field."""
    cleaned = text.strip()
    for pattern, placeholder in _SCRUB_PATTERNS:
        cleaned = pattern.sub(placeholder, cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def canonical_capability(raw_capability: str) -> str:
    """Scrub identifiers, then normalize a free-text capability to a stable slug;
    placeholder when empty and collision-resistant shortening when oversized."""
    capability = slugify(_scrub_identifiers(raw_capability)) or GENERAL_CAPABILITY
    if len(capability) <= MAX_CAPABILITY_LEN:
        return capability
    suffix = sha256(capability.encode("utf-8")).hexdigest()[:_HASH_SUFFIX_LEN]
    prefix = capability[: MAX_CAPABILITY_LEN - _HASH_SUFFIX_LEN - 1].rstrip("-")
    return f"{prefix}-{suffix}"


def build_topic_key(area: Area, intent: Intent, capability_slug: str) -> str:
    """Compose the groupable aggregation key ``area/intent/capability``."""
    topic_key = f"{area.value}/{intent.value}/{capability_slug}"
    if len(topic_key) > MAX_TOPIC_KEY_LEN:
        raise ValueError("Canonical topic key exceeds its persistence limit")
    return topic_key


def sanitize_label(topic: str) -> str:
    """Scrub identifiers from the human-readable topic label and length-cap it."""
    cleaned = _scrub_identifiers(topic)
    return cleaned[:_MAX_SUMMARY_LEN]


def sanitize_summary(summary: str) -> str:
    """Strip identifiers and truncate so the stored insight carries no raw payload."""
    cleaned = _scrub_identifiers(summary)
    if len(cleaned) > _MAX_SUMMARY_LEN:
        cleaned = cleaned[:_MAX_SUMMARY_LEN].rstrip() + "…"
    return cleaned


@dataclass(frozen=True)
class CanonicalTopic:
    """A per-turn proposal reduced to its groupable key plus insight fields."""

    area: Area
    intent: Intent
    capability: str
    topic_key: str
    label: str
    summary: str
    confidence: float


def canonicalize(
    *, area: Area, intent: Intent, capability: str, topic: str, summary: str, confidence: float
) -> CanonicalTopic:
    """Reduce a model proposal to a canonical, best-effort-scrubbed topic assignment."""
    capability_slug = canonical_capability(capability)
    return CanonicalTopic(
        area=area,
        intent=intent,
        capability=capability_slug,
        topic_key=build_topic_key(area, intent, capability_slug),
        label=sanitize_label(topic),
        summary=sanitize_summary(summary),
        confidence=confidence,
    )
