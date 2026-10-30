"""Accumulate per-conversation topic assignments and derive the reporting snapshot.

The durable unit is a ``(conversation_hash, topic_key)`` assignment: one row per topic
a conversation touched, with a cumulative turn count. Seeding from previously stored
assignments lets an incremental run (which only classifies new turns) keep cumulative
counts correct while still computing the full-picture aggregate.

The aggregate groups all assignments by ``topic_key``. Because each assignment is unique
per conversation, the number of assignments for a topic IS its distinct-conversation
count — the primary product metric.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from conversation_segmentation.canonicalizer import CanonicalTopic
from conversation_segmentation.taxonomy import TAXONOMY_VERSION

_MAX_EXAMPLES = 3


class TaxonomyVersionMismatchError(ValueError):
    """Persisted assignments require an explicit taxonomy migration before processing."""


@dataclass
class AssignmentState:
    """Cumulative state of one (conversation, topic) pair."""

    conversation_hash: str
    topic_key: str
    area: str
    intent: str
    capability: str
    label: str
    summary: str
    confidence: float
    turn_count: int
    # Taxonomy version under which this assignment was last classified. Stored so a
    # future taxonomy change can filter or re-canonicalize rows left on an older version
    # instead of silently combining incomparable classifications in the aggregate.
    taxonomy_version: str = TAXONOMY_VERSION


@dataclass
class TopicTally:
    """Collect topic assignments across a run and emit assignment + aggregate rows."""

    _assignments: dict[tuple[str, str], AssignmentState] = field(default_factory=dict)
    _touched: set[tuple[str, str]] = field(default_factory=set)
    total_turns: int = 0
    failed_turns: int = 0

    def seed(self, prior: list[AssignmentState]) -> None:
        """Load previously stored assignments so cumulative counts survive restarts."""
        stale_versions = {state.taxonomy_version for state in prior if state.taxonomy_version != TAXONOMY_VERSION}
        if stale_versions:
            versions = ", ".join(sorted(stale_versions))
            raise TaxonomyVersionMismatchError(
                f"Persisted assignment taxonomy ({versions}) does not match current taxonomy ({TAXONOMY_VERSION})"
            )
        for state in prior:
            self._assignments[(state.conversation_hash, state.topic_key)] = state

    def add_turn(self, conversation_hash: str, topic: CanonicalTopic) -> None:
        """Record one classified turn under its conversation and canonical topic."""
        self.total_turns += 1
        key = (conversation_hash, topic.topic_key)
        self._touched.add(key)
        existing = self._assignments.get(key)
        if existing is None:
            self._assignments[key] = AssignmentState(
                conversation_hash=conversation_hash,
                topic_key=topic.topic_key,
                area=topic.area.value,
                intent=topic.intent.value,
                capability=topic.capability,
                label=topic.label,
                summary=topic.summary,
                confidence=topic.confidence,
                turn_count=1,
                taxonomy_version=TAXONOMY_VERSION,
            )
            return
        existing.turn_count += 1
        current_rank = (existing.confidence, existing.label, existing.summary)
        candidate_rank = (topic.confidence, topic.label, topic.summary)
        if candidate_rank > current_rank:  # deterministic winner even when confidence ties
            existing.confidence = topic.confidence
            existing.label = topic.label
            existing.summary = topic.summary

    def add_failure(self) -> None:
        """Record a turn that failed to classify (counts toward total, not any topic)."""
        self.failed_turns += 1
        self.total_turns += 1

    def drain_touched(self) -> list[AssignmentState]:
        """Return assignments changed since the last drain, then clear the change set.

        Lets a run checkpoint progress in batches: each drained batch is persisted
        and the tracker reset, so the next flush carries only newly-changed
        assignments rather than everything touched so far.
        """
        drained = [self._assignments[key] for key in self._touched]
        self._touched.clear()
        return drained

    def aggregate_rows(self) -> list[dict]:
        """Group all assignments by topic_key into reporting rows (distinct conversations)."""
        groups: dict[str, list[AssignmentState]] = {}
        for state in self._assignments.values():
            groups.setdefault(state.topic_key, []).append(state)

        rows: list[dict] = []
        for topic_key, states in groups.items():
            best = max(states, key=lambda s: (s.confidence, s.label, s.summary, s.conversation_hash))
            examples = [
                state.summary
                for state in sorted(states, key=lambda s: (-s.confidence, s.summary, s.conversation_hash))
                if state.summary
            ]
            rows.append(
                {
                    "TOPIC_KEY": topic_key,
                    "AREA": best.area,
                    "INTENT": best.intent,
                    "CAPABILITY": best.capability,
                    "TOPIC_LABEL": best.label,
                    "DISTINCT_CONVERSATION_COUNT": len(states),
                    "TURN_COUNT": sum(s.turn_count for s in states),
                    "EXAMPLE_SUMMARIES": _dedupe(examples)[:_MAX_EXAMPLES],
                    "TAXONOMY_VERSION": TAXONOMY_VERSION,
                }
            )
        rows.sort(key=lambda r: (-r["DISTINCT_CONVERSATION_COUNT"], r["TOPIC_KEY"]))
        return rows


def _dedupe(items: list[str]) -> list[str]:
    """Preserve order, drop duplicates."""
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
