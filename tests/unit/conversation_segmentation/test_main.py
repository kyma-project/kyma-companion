import datetime as dt
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from conversation_segmentation import watermark
from conversation_segmentation.hana_writer import _META_COLUMNS
from conversation_segmentation.main import run_segmentation
from conversation_segmentation.taxonomy import Category, Judgement, crosstab_columns

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_only_new_turns_segmented_and_row_written(monkeypatch):
    convo = json.dumps(
        [
            {"type": "human", "content": "q1"},
            {"type": "ai", "content": "a1"},
            {"type": "human", "content": "q2"},
            {"type": "ai", "content": "a2"},
        ]
    )  # 2 turns
    rconn = MagicMock()

    async def _iter(match):
        yield "kyma_agent_conversation:s1"

    rconn.scan_iter = _iter
    rconn.get = AsyncMock(return_value=convo)

    hconn = MagicMock()
    cur = MagicMock()
    hconn.cursor.return_value.__enter__.return_value = cur
    # watermark already at 1 → only the 2nd turn is new; fingerprint must match so count applies
    turns_for_fp = [{"turn_index": 0, "query": "q1", "response": "a1"}]
    monkeypatch.setattr(
        "conversation_segmentation.main.read_watermarks",
        lambda c, s: {watermark.session_key("s1"): (1, watermark.head_fingerprint(turns_for_fp))},
    )
    monkeypatch.setattr("conversation_segmentation.main.ensure_tables", lambda c, s: None)
    written = {}
    monkeypatch.setattr(
        "conversation_segmentation.main.write_run", lambda c, s, row, wm, pb: written.update(row=row, wm=wm)
    )

    seg = MagicMock()
    seg.segment_turn = AsyncMock(return_value=(Category.TROUBLESHOOTING, Judgement.SUFFICIENT))
    seg.tokens = {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6}

    row = await run_segmentation(
        redis_conn=rconn,
        hana_conn=hconn,
        segmenter=seg,
        schema="AIFORCE2",
        landscape="dev",
        now=dt.datetime(2026, 9, 10),
    )
    assert seg.segment_turn.await_count == 1  # only the 1 new turn
    assert row["TOTAL_TURNS"] == 1 and row["FAILED_TURNS"] == 0
    assert row["C_TROUBLESHOOTING_SUFFICIENT"] == 1 and row["SEG_MODEL"]
    assert written["wm"][watermark.session_key("s1")][0] == 2  # noqa: PLR2004  # advanced to full count


@pytest.mark.asyncio
async def test_skip_and_count_failure_path(monkeypatch):
    """First turn succeeds, second raises RuntimeError; failure counted, watermark still advanced."""
    convo = json.dumps(
        [
            {"type": "human", "content": "q1"},
            {"type": "ai", "content": "a1"},
            {"type": "human", "content": "q2"},
            {"type": "ai", "content": "a2"},
        ]
    )  # 2 turns
    rconn = MagicMock()

    async def _iter(match):
        yield "kyma_agent_conversation:s1"

    rconn.scan_iter = _iter
    rconn.get = AsyncMock(return_value=convo)

    hconn = MagicMock()
    cur = MagicMock()
    hconn.cursor.return_value.__enter__.return_value = cur
    # watermark empty → both turns are new
    monkeypatch.setattr("conversation_segmentation.main.read_watermarks", lambda c, s: {})
    monkeypatch.setattr("conversation_segmentation.main.ensure_tables", lambda c, s: None)
    written = {}
    monkeypatch.setattr(
        "conversation_segmentation.main.write_run", lambda c, s, row, wm, pb: written.update(row=row, wm=wm)
    )

    seg = MagicMock()
    seg.segment_turn = AsyncMock(
        side_effect=[(Category.TROUBLESHOOTING, Judgement.SUFFICIENT), RuntimeError("llm down")]
    )
    seg.tokens = {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6}

    row = await run_segmentation(
        redis_conn=rconn,
        hana_conn=hconn,
        segmenter=seg,
        schema="AIFORCE2",
        landscape="dev",
        now=dt.datetime(2026, 9, 10),
    )
    assert row["TOTAL_TURNS"] == 2  # noqa: PLR2004
    assert row["FAILED_TURNS"] == 1  # noqa: PLR2004
    assert row["C_TROUBLESHOOTING_SUFFICIENT"] == 1  # noqa: PLR2004
    assert written["wm"][watermark.session_key("s1")][0] == 2  # noqa: PLR2004  # advanced despite failure

    # Fix 3: agg_row keys must exactly match the HANA schema (meta + crosstab)
    meta_names = {c.split()[0] for c in _META_COLUMNS}
    assert set(row.keys()) == meta_names | set(crosstab_columns())


@pytest.mark.asyncio
async def test_empty_parse_preserves_prior_watermark(monkeypatch):
    """A transient malformed JSON (parse → []) must not clobber a valid prior watermark to (0, "")."""
    rconn = MagicMock()

    async def _iter(match):
        yield "kyma_agent_conversation:s1"

    rconn.scan_iter = _iter
    rconn.get = AsyncMock(return_value="}{ not valid json")  # parse_messages → []

    hconn = MagicMock()
    cur = MagicMock()
    hconn.cursor.return_value.__enter__.return_value = cur

    key = watermark.session_key("s1")
    monkeypatch.setattr(
        "conversation_segmentation.main.read_watermarks",
        lambda c, s: {key: (2, "realfp")},  # valid prior: 2 turns already segmented
    )
    monkeypatch.setattr("conversation_segmentation.main.ensure_tables", lambda c, s: None)
    written = {}
    monkeypatch.setattr(
        "conversation_segmentation.main.write_run", lambda c, s, row, wm, pb: written.update(row=row, wm=wm)
    )

    seg = MagicMock()
    seg.segment_turn = AsyncMock()
    seg.tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    row = await run_segmentation(
        redis_conn=rconn,
        hana_conn=hconn,
        segmenter=seg,
        schema="AIFORCE2",
        landscape="dev",
        now=dt.datetime(2026, 9, 10),
    )
    seg.segment_turn.assert_not_awaited()  # nothing to segment
    assert row["TOTAL_TURNS"] == 0
    assert key not in written["wm"]  # prior (2, "realfp") left intact, not overwritten with (0, "")
    """A stale watermark with a non-matching fingerprint resets already=0 (re-segments everything)."""
    convo = json.dumps(
        [
            {"type": "human", "content": "q1"},
            {"type": "ai", "content": "a1"},
            {"type": "human", "content": "q2"},
            {"type": "ai", "content": "a2"},
        ]
    )  # 2 turns
    rconn = MagicMock()

    async def _iter(match):
        yield "kyma_agent_conversation:s1"

    rconn.scan_iter = _iter
    rconn.get = AsyncMock(return_value=convo)

    hconn = MagicMock()
    cur = MagicMock()
    hconn.cursor.return_value.__enter__.return_value = cur

    # Stale watermark: count=5, fingerprint is all-zeros (will not match the real first-turn fp)
    stale_fp = "0" * 64
    monkeypatch.setattr(
        "conversation_segmentation.main.read_watermarks",
        lambda c, s: {watermark.session_key("s1"): (5, stale_fp)},
    )
    monkeypatch.setattr("conversation_segmentation.main.ensure_tables", lambda c, s: None)
    written = {}
    monkeypatch.setattr(
        "conversation_segmentation.main.write_run", lambda c, s, row, wm, pb: written.update(row=row, wm=wm)
    )

    seg = MagicMock()
    seg.segment_turn = AsyncMock(return_value=(Category.TROUBLESHOOTING, Judgement.SUFFICIENT))
    seg.tokens = {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6}

    row = await run_segmentation(
        redis_conn=rconn,
        hana_conn=hconn,
        segmenter=seg,
        schema="AIFORCE2",
        landscape="dev",
        now=dt.datetime(2026, 9, 10),
    )
    # Despite stale count=5, fp mismatch resets already=0, so all 2 turns are segmented
    assert seg.segment_turn.await_count == 2  # noqa: PLR2004
    assert row["TOTAL_TURNS"] == 2  # noqa: PLR2004
    assert row["FAILED_TURNS"] == 0
    key = watermark.session_key("s1")
    assert written["wm"][key][0] == 2  # noqa: PLR2004  # count reset to actual length
    # Fingerprint is now the real one (not the stale zeros)
    turns_real = [{"turn_index": 0, "query": "q1", "response": "a1"}]
    assert written["wm"][key][1] == watermark.head_fingerprint(turns_real)
