import datetime as dt
import json
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from conversation_segmentation import watermark
from conversation_segmentation.canonicalizer import canonicalize
from conversation_segmentation.main import _enforce_log_privacy, run_segmentation
from conversation_segmentation.taxonomy import Area, Intent

pytestmark = pytest.mark.unit


def test_enforce_log_privacy_pins_root_and_silences_payload_loggers():
    """A mounted DEBUG config must not let HTTP/SDK loggers dump request bodies."""
    logging.getLogger().setLevel(logging.DEBUG)
    logging.getLogger("botocore").setLevel(logging.DEBUG)
    try:
        _enforce_log_privacy()
        assert logging.getLogger().level == logging.INFO
        for name in ("botocore", "boto3", "urllib3", "httpx", "httpcore"):
            assert logging.getLogger(name).level == logging.WARNING
    finally:
        logging.getLogger().setLevel(logging.WARNING)


def _topic():
    return canonicalize(
        area=Area.ISTIO,
        intent=Intent.TROUBLESHOOTING,
        capability="mtls",
        topic="mTLS",
        summary="user debugging mtls",
        confidence=0.9,
    )


def _two_turn_convo():
    return json.dumps(
        [
            {"type": "human", "content": "q1"},
            {"type": "ai", "content": "a1"},
            {"type": "human", "content": "q2"},
            {"type": "ai", "content": "a2"},
        ]
    )


def _redis_with(convo):
    rconn = MagicMock()

    async def _iter(match):
        yield "kyma_agent_conversation:s1"

    rconn.scan_iter = _iter
    rconn.get = AsyncMock(return_value=convo)
    return rconn


def _hana():
    hconn = MagicMock()
    cur = MagicMock()
    hconn.cursor.return_value.__enter__.return_value = cur
    return hconn


def _patch_io(monkeypatch, *, watermarks, assignments=None):
    monkeypatch.setattr("conversation_segmentation.main.read_watermarks", lambda c, s: watermarks)
    monkeypatch.setattr("conversation_segmentation.main.read_assignments", lambda c, s: assignments or [])
    monkeypatch.setattr("conversation_segmentation.main.ensure_tables", lambda c, s: None)
    monkeypatch.setattr("conversation_segmentation.main.validate_taxonomy_version", lambda c, s: None)
    captured: dict = {"watermarks": {}, "assignments": [], "batch_calls": 0}

    def _batch(c, s, *, assignments, watermarks, run_id, now):
        captured["batch_calls"] += 1
        captured["watermarks"].update(watermarks)
        captured["assignments"].extend(assignments)
        captured["run_id"] = run_id

    def _run(c, s, **kwargs):
        captured.update(kwargs)

    monkeypatch.setattr("conversation_segmentation.main.write_batch", _batch)
    monkeypatch.setattr("conversation_segmentation.main.write_run", _run)
    return captured


@pytest.mark.asyncio
async def test_only_new_turns_analyzed_and_snapshot_written(monkeypatch):
    turns_for_fp = [{"turn_index": 0, "query": "q1", "response": "a1"}]
    captured = _patch_io(
        monkeypatch,
        watermarks={watermark.session_key("s1"): (1, watermark.head_fingerprint(turns_for_fp))},
    )
    seg = MagicMock()
    seg.segment_turn = AsyncMock(return_value=_topic())
    seg.tokens = {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6}

    row = await run_segmentation(
        redis_conn=_redis_with(_two_turn_convo()),
        hana_conn=_hana(),
        segmenter=seg,
        schema="AIFORCE2",
        now=dt.datetime(2026, 9, 10),
    )
    assert seg.segment_turn.await_count == 1  # only the 1 new turn
    assert row["TURNS_ANALYZED"] == 1 and row["FAILED_TURNS"] == 0
    assert row["SEG_MODEL"] and row["TAXONOMY_VERSION"]
    assert captured["watermarks"][watermark.session_key("s1")][0] == 2  # noqa: PLR2004  # advanced to full count
    agg = captured["aggregate_rows"]
    assert len(agg) == 1 and agg[0]["TOPIC_KEY"] == "istio/troubleshooting/mtls"
    assert agg[0]["DISTINCT_CONVERSATION_COUNT"] == 1


@pytest.mark.asyncio
async def test_skip_and_count_failure_path(monkeypatch):
    captured = _patch_io(monkeypatch, watermarks={})
    seg = MagicMock()
    seg.segment_turn = AsyncMock(side_effect=[_topic(), RuntimeError("llm down")])
    seg.tokens = {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6}

    row = await run_segmentation(
        redis_conn=_redis_with(_two_turn_convo()),
        hana_conn=_hana(),
        segmenter=seg,
        schema="AIFORCE2",
        now=dt.datetime(2026, 9, 10),
    )
    assert row["TURNS_ANALYZED"] == 2 and row["FAILED_TURNS"] == 1  # noqa: PLR2004
    assert captured["watermarks"][watermark.session_key("s1")][0] == 1  # retry the failed second turn next run
    assert captured["aggregate_rows"][0]["TURN_COUNT"] == 1  # only the successful turn counted


@pytest.mark.asyncio
async def test_cumulative_turn_count_from_seeded_assignments(monkeypatch):
    from conversation_segmentation.aggregator import AssignmentState

    turns_for_fp = [{"turn_index": 0, "query": "q1", "response": "a1"}]
    prior_assignment = AssignmentState(
        conversation_hash=watermark.conversation_instance_key("s1", watermark.head_fingerprint(turns_for_fp)),
        topic_key="istio/troubleshooting/mtls",
        area="istio",
        intent="troubleshooting",
        capability="mtls",
        label="mTLS",
        summary="s",
        confidence=0.9,
        turn_count=3,
    )
    captured = _patch_io(monkeypatch, watermarks={}, assignments=[prior_assignment])
    seg = MagicMock()
    seg.segment_turn = AsyncMock(return_value=_topic())
    seg.tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    await run_segmentation(
        redis_conn=_redis_with(_two_turn_convo()),
        hana_conn=_hana(),
        segmenter=seg,
        schema="AIFORCE2",
        now=dt.datetime(2026, 9, 10),
    )
    # 3 prior + 2 new turns on the same topic = 5, still one distinct conversation
    agg = captured["aggregate_rows"][0]
    assert agg["TURN_COUNT"] == 5 and agg["DISTINCT_CONVERSATION_COUNT"] == 1  # noqa: PLR2004


@pytest.mark.asyncio
async def test_empty_parse_preserves_prior_watermark(monkeypatch):
    """A transient malformed JSON (parse → []) must not clobber a valid prior watermark."""
    key = watermark.session_key("s1")
    captured = _patch_io(monkeypatch, watermarks={key: (2, "realfp")})
    seg = MagicMock()
    seg.segment_turn = AsyncMock()
    seg.tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    row = await run_segmentation(
        redis_conn=_redis_with("}{ not valid json"),
        hana_conn=_hana(),
        segmenter=seg,
        schema="AIFORCE2",
        now=dt.datetime(2026, 9, 10),
    )
    seg.segment_turn.assert_not_awaited()
    assert row["TURNS_ANALYZED"] == 0
    assert key not in captured["watermarks"]  # prior (2, "realfp") left intact


@pytest.mark.asyncio
async def test_stale_fingerprint_reanalyzes_all_turns(monkeypatch):
    """A stale watermark whose fingerprint no longer matches resets already=0."""
    stale_fp = "0" * 64
    captured = _patch_io(monkeypatch, watermarks={watermark.session_key("s1"): (5, stale_fp)})
    seg = MagicMock()
    seg.segment_turn = AsyncMock(return_value=_topic())
    seg.tokens = {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6}

    row = await run_segmentation(
        redis_conn=_redis_with(_two_turn_convo()),
        hana_conn=_hana(),
        segmenter=seg,
        schema="AIFORCE2",
        now=dt.datetime(2026, 9, 10),
    )
    assert seg.segment_turn.await_count == 2  # noqa: PLR2004  # fp mismatch → all turns re-analysed
    assert row["TURNS_ANALYZED"] == 2  # noqa: PLR2004
    key = watermark.session_key("s1")
    turns_real = [{"turn_index": 0, "query": "q1", "response": "a1"}]
    assert captured["watermarks"][key] == (2, watermark.head_fingerprint(turns_real))


def test_reused_session_id_has_a_distinct_assignment_identity():
    old_fp = watermark.head_fingerprint([{"query": "old", "response": "answer"}])
    new_fp = watermark.head_fingerprint([{"query": "new", "response": "answer"}])

    assert watermark.conversation_instance_key("s1", old_fp) != watermark.conversation_instance_key("s1", new_fp)


@pytest.mark.asyncio
async def test_failure_logging_omits_exception_content(monkeypatch, caplog):
    """A failed turn must log only the exception type, never its (content-derived) message."""
    _patch_io(monkeypatch, watermarks={})
    seg = MagicMock()
    secret = "user said: my token is abcSECRET in namespace prod-9"
    seg.segment_turn = AsyncMock(side_effect=ValueError(secret))
    seg.tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    with caplog.at_level("WARNING", logger="conversation_segmentation"):
        await run_segmentation(
            redis_conn=_redis_with(_two_turn_convo()),
            hana_conn=_hana(),
            segmenter=seg,
            schema="AIFORCE2",
            now=dt.datetime(2026, 9, 10),
        )
    assert "ValueError" in caplog.text  # type is logged
    assert secret not in caplog.text  # content is not


def _redis_with_many(count):
    rconn = MagicMock()
    sessions = [f"s{i:02d}" for i in range(count)]

    async def _iter(match):
        for s in sessions:
            yield f"kyma_agent_conversation:{s}"

    convo = json.dumps([{"type": "human", "content": "q"}, {"type": "ai", "content": "a"}])
    rconn.scan_iter = _iter
    rconn.get = AsyncMock(return_value=convo)
    return rconn, sessions


@pytest.mark.asyncio
async def test_progress_checkpointed_in_batches(monkeypatch):
    """With BATCH_SIZE=2 over 5 conversations, write_batch is called per batch plus a final flush."""
    monkeypatch.setattr("conversation_segmentation.main.config.BATCH_SIZE", 2)
    captured = _patch_io(monkeypatch, watermarks={})
    rconn, sessions = _redis_with_many(5)
    seg = MagicMock()
    seg.segment_turn = AsyncMock(return_value=_topic())
    seg.tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    row = await run_segmentation(
        redis_conn=rconn,
        hana_conn=_hana(),
        segmenter=seg,
        schema="AIFORCE2",
        now=dt.datetime(2026, 9, 10),
    )
    # 5 conversations, batch size 2 → flushes after conv 2 and 4, plus one final flush = 3
    assert captured["batch_calls"] == 3  # noqa: PLR2004
    assert row["TURNS_ANALYZED"] == 5  # noqa: PLR2004
    # every session's watermark eventually checkpointed
    assert {watermark.session_key(s) for s in sessions} == set(captured["watermarks"])
    # run_id is stable across batches and the final run row
    assert captured["run_id"] == row["RUN_ID"]


@pytest.mark.asyncio
async def test_committed_batches_survive_a_later_crash(monkeypatch):
    """A failure after some batches commit must leave those batches durable (not rolled back)."""
    monkeypatch.setattr("conversation_segmentation.main.config.BATCH_SIZE", 1)
    monkeypatch.setattr("conversation_segmentation.main.read_watermarks", lambda c, s: {})
    monkeypatch.setattr("conversation_segmentation.main.read_assignments", lambda c, s: [])
    monkeypatch.setattr("conversation_segmentation.main.ensure_tables", lambda c, s: None)
    monkeypatch.setattr("conversation_segmentation.main.validate_taxonomy_version", lambda c, s: None)
    committed: list[str] = []

    def _batch(c, s, *, assignments, watermarks, run_id, now):
        if len(committed) >= 2:  # third batch "crashes"  # noqa: PLR2004
            raise RuntimeError("hana down mid-batch")
        committed.extend(watermarks)

    monkeypatch.setattr("conversation_segmentation.main.write_batch", _batch)
    monkeypatch.setattr("conversation_segmentation.main.write_run", lambda c, s, **k: None)
    rconn, _ = _redis_with_many(5)
    seg = MagicMock()
    seg.segment_turn = AsyncMock(return_value=_topic())
    seg.tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    with pytest.raises(RuntimeError):
        await run_segmentation(
            redis_conn=rconn,
            hana_conn=_hana(),
            segmenter=seg,
            schema="AIFORCE2",
            now=dt.datetime(2026, 9, 10),
        )
    assert len(committed) == 2  # noqa: PLR2004  # first two batches durable; a re-run resumes from them
