"""Tests for the topic tally: distinct-conversation counting and cumulative turns."""

import pytest

from conversation_segmentation.aggregator import AssignmentState, TaxonomyVersionMismatchError, TopicTally
from conversation_segmentation.canonicalizer import canonicalize
from conversation_segmentation.taxonomy import TAXONOMY_VERSION, Area, Intent

pytestmark = pytest.mark.unit


def _topic(area, intent, capability, topic="t", summary="s", confidence=0.9):
    return canonicalize(
        area=area, intent=intent, capability=capability, topic=topic, summary=summary, confidence=confidence
    )


def test_assignment_records_current_taxonomy_version():
    tally = TopicTally()
    tally.add_turn("conv-a", _topic(Area.ISTIO, Intent.TROUBLESHOOTING, "mtls"))
    assert tally.drain_touched()[0].taxonomy_version == TAXONOMY_VERSION


def test_seed_rejects_an_assignment_from_an_old_taxonomy():
    tally = TopicTally()
    old_assignment = AssignmentState(
        conversation_hash="conv-a",
        topic_key="istio/troubleshooting/mtls",
        area="istio",
        intent="troubleshooting",
        capability="mtls",
        label="t",
        summary="s",
        confidence=0.9,
        turn_count=2,
        taxonomy_version="v0",
    )

    with pytest.raises(TaxonomyVersionMismatchError, match="v0.*v1"):
        tally.seed([old_assignment])


def test_multiple_turns_one_conversation_count_as_one_distinct_conversation():
    tally = TopicTally()
    mtls = _topic(Area.ISTIO, Intent.TROUBLESHOOTING, "mtls")
    tally.add_turn("conv-a", mtls)
    tally.add_turn("conv-a", mtls)  # same conversation, same topic
    tally.add_turn("conv-a", mtls)

    rows = tally.aggregate_rows()
    assert len(rows) == 1
    assert rows[0]["DISTINCT_CONVERSATION_COUNT"] == 1
    assert rows[0]["TURN_COUNT"] == 3  # noqa: PLR2004
    assert tally.total_turns == 3  # noqa: PLR2004


def test_two_conversations_same_topic_increment_distinct_count_by_two():
    tally = TopicTally()
    tally.add_turn("conv-a", _topic(Area.ISTIO, Intent.TROUBLESHOOTING, "mtls"))
    tally.add_turn("conv-b", _topic(Area.ISTIO, Intent.TROUBLESHOOTING, "mTLS"))  # same slug

    rows = tally.aggregate_rows()
    assert len(rows) == 1
    assert rows[0]["TOPIC_KEY"] == "istio/troubleshooting/mtls"
    assert rows[0]["DISTINCT_CONVERSATION_COUNT"] == 2  # noqa: PLR2004


def test_istio_and_serverless_are_separate_rows():
    tally = TopicTally()
    tally.add_turn("conv-a", _topic(Area.ISTIO, Intent.TROUBLESHOOTING, "mtls"))
    tally.add_turn("conv-b", _topic(Area.SERVERLESS, Intent.TROUBLESHOOTING, "build"))

    rows = tally.aggregate_rows()
    keys = {r["TOPIC_KEY"] for r in rows}
    assert keys == {"istio/troubleshooting/mtls", "serverless/troubleshooting/build"}


def test_seed_makes_turn_counts_cumulative_across_runs():
    tally = TopicTally()
    tally.seed(
        [
            AssignmentState(
                conversation_hash="conv-a",
                topic_key="istio/troubleshooting/mtls",
                area="istio",
                intent="troubleshooting",
                capability="mtls",
                label="t",
                summary="s",
                confidence=0.9,
                turn_count=2,
            )
        ]
    )
    tally.add_turn("conv-a", _topic(Area.ISTIO, Intent.TROUBLESHOOTING, "mtls"))

    rows = tally.aggregate_rows()
    assert rows[0]["TURN_COUNT"] == 3  # 2 prior + 1 new  # noqa: PLR2004
    assert rows[0]["DISTINCT_CONVERSATION_COUNT"] == 1
    # only the touched assignment is returned for upsert
    assert len(tally.drain_touched()) == 1


def test_examples_are_deduped_and_capped():
    tally = TopicTally()
    for i in range(5):
        tally.add_turn(f"conv-{i}", _topic(Area.ISTIO, Intent.TROUBLESHOOTING, "mtls", summary=f"summary {i % 2}"))
    rows = tally.aggregate_rows()
    assert rows[0]["DISTINCT_CONVERSATION_COUNT"] == 5  # noqa: PLR2004
    assert len(rows[0]["EXAMPLE_SUMMARIES"]) == 2  # two distinct summaries, capped at 3  # noqa: PLR2004


def test_failures_count_toward_total_only():
    tally = TopicTally()
    tally.add_turn("conv-a", _topic(Area.ISTIO, Intent.TROUBLESHOOTING, "mtls"))
    tally.add_failure()
    assert tally.total_turns == 2 and tally.failed_turns == 1  # noqa: PLR2004
    assert tally.aggregate_rows()[0]["DISTINCT_CONVERSATION_COUNT"] == 1


def test_drain_touched_returns_changes_since_last_drain_then_clears():
    tally = TopicTally()
    tally.add_turn("conv-a", _topic(Area.ISTIO, Intent.TROUBLESHOOTING, "mtls"))
    first = tally.drain_touched()
    assert {s.conversation_hash for s in first} == {"conv-a"}
    assert tally.drain_touched() == []  # nothing changed since last drain

    tally.add_turn("conv-b", _topic(Area.SERVERLESS, Intent.TROUBLESHOOTING, "build"))
    second = tally.drain_touched()
    assert {s.conversation_hash for s in second} == {"conv-b"}  # only the new change, not conv-a again
    # draining does not drop history: the aggregate still sees both conversations
    assert len(tally.aggregate_rows()) == 2  # noqa: PLR2004
