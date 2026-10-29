"""Entrypoint for the conversation topic-analysis job.

Run in the Companion image as:  python3.14 -m conversation_segmentation.main segment

Reads Companion conversations from Redis, classifies only-new turns into dynamic Kyma
topics, and persists durable per-conversation topic assignments plus a cumulative
aggregate snapshot to HANA. The primary output is the distinct-conversation count per
topic. No raw conversation text, session id, or model reasoning is persisted.
"""

import argparse
import asyncio
import contextlib
import datetime as dt
import logging
import uuid
from typing import Any

from conversation_segmentation import config
from conversation_segmentation.aggregator import TopicTally
from conversation_segmentation.hana_writer import (
    ensure_tables,
    read_assignments,
    read_last_window_end,
    read_watermarks,
    validate_taxonomy_version,
    write_batch,
    write_run,
)
from conversation_segmentation.redis_reader import iter_conversations, pair_turns, parse_messages
from conversation_segmentation.segmenter import Segmenter
from conversation_segmentation.taxonomy import TAXONOMY_VERSION
from conversation_segmentation.watermark import (
    conversation_instance_key,
    head_fingerprint,
    select_new_turns,
    session_key,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("conversation_segmentation")

# HTTP/SDK client libraries dump full request bodies — bearer tokens and raw
# query/response text — at DEBUG. This job must never emit those, so they are pinned
# to WARNING regardless of the effective root level (see _enforce_log_privacy).
_NOISY_PAYLOAD_LOGGERS = (
    "botocore",
    "boto3",
    "urllib3",
    "httpx",
    "httpcore",
    "openai",
    "anthropic",
    "redis",
    "hdbcli",
)


def _enforce_log_privacy() -> None:
    """Keep this batch job's logs free of credentials and raw conversation text.

    The shared Companion config can set ``LOG_LEVEL=DEBUG``, and ``load_env_from_json``
    makes that value win over the pod environment, which drives the app's root logger to
    DEBUG when app services are imported. At DEBUG the HTTP/SDK client libraries dump full
    request bodies — bearer tokens and raw conversation text — to stdout. Pin the root
    logger back to INFO and force the known payload-dumping libraries to WARNING so the
    job only ever logs its own progress counts.
    """
    logging.getLogger().setLevel(logging.INFO)
    for name in _NOISY_PAYLOAD_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


async def run_segmentation(
    *, redis_conn: Any, hana_conn: Any, segmenter: Any, schema: str, now: dt.datetime
) -> dict[str, Any]:
    """Analyse only-new turns for every live conversation and write one run snapshot.

    Conversation payloads are streamed one at a time and progress is checkpointed to
    HANA every ``config.BATCH_SIZE`` conversations, so a crash loses at most one batch.
    Session IDs, watermarks, and cumulative assignments are still held for the run and
    therefore scale with retained corpus size.
    """
    ensure_tables(hana_conn, schema)
    validate_taxonomy_version(hana_conn, schema)
    prior = read_watermarks(hana_conn, schema)
    tally = TopicTally()
    tally.seed(read_assignments(hana_conn, schema))
    run_id = uuid.uuid4().hex  # unique per run; no collision when two runs share a second
    pending_watermarks: dict[str, tuple[int, str]] = {}
    batch_count = 0

    log.info(
        "Starting topic analysis: limit=%d batch_size=%d taxonomy=%s",
        config.MAX_CONVERSATIONS,
        config.BATCH_SIZE,
        TAXONOMY_VERSION,
    )
    processed_turns = 0
    conversation_number = 0
    async for session_id, raw_json in iter_conversations(
        redis_conn, config.CONVERSATION_KEY_PREFIX, max_conversations=config.MAX_CONVERSATIONS
    ):
        conversation_number += 1
        turns = pair_turns(parse_messages(raw_json))
        watermark_key = session_key(session_id)
        cur_fp = head_fingerprint(turns)
        conversation_hash = conversation_instance_key(session_id, cur_fp)
        prior_count, prior_fp = prior.get(watermark_key, (0, ""))
        already = prior_count if cur_fp == prior_fp else 0
        new_turns = select_new_turns(turns, already)
        log.info(
            "Conversation %d: complete_turns=%d new_turns=%d",
            conversation_number,
            len(turns),
            len(new_turns),
        )
        watermark_count, processed_turns = await _classify_new_turns(
            segmenter=segmenter,
            tally=tally,
            conversation_hash=conversation_hash,
            turns=new_turns,
            already=already,
            conversation_number=conversation_number,
            processed_turns=processed_turns,
        )
        if turns or prior_count == 0:
            pending_watermarks[watermark_key] = (watermark_count, cur_fp)
        # else: empty parse (transient malformed JSON) with a valid prior — keep it, don't clobber to (0, "")
        batch_count += 1
        if batch_count >= config.BATCH_SIZE:
            _flush_batch(hana_conn, schema, tally, pending_watermarks, run_id, now)
            pending_watermarks = {}
            batch_count = 0

    _flush_batch(hana_conn, schema, tally, pending_watermarks, run_id, now)  # final partial batch

    run_row = _build_run_row(hana_conn, schema, tally, segmenter, now, run_id)
    aggregate_rows = tally.aggregate_rows()
    write_run(
        hana_conn,
        schema,
        run_row=run_row,
        aggregate_rows=aggregate_rows,
        now=now,
    )
    log.info(
        "Wrote run: turns=%d failed=%d conversations=%d topics=%d",
        tally.total_turns,
        tally.failed_turns,
        conversation_number,
        len(aggregate_rows),
    )
    return run_row


async def _classify_new_turns(
    *,
    segmenter: Any,
    tally: TopicTally,
    conversation_hash: str,
    turns: list[dict],
    already: int,
    conversation_number: int,
    processed_turns: int,
) -> tuple[int, int]:
    """Classify a contiguous turn prefix, stopping at a failure so it can be retried."""
    watermark_count = already
    for turn in turns:
        failed = False
        try:
            topic = await segmenter.segment_turn(turn["query"], turn["response"])
            tally.add_turn(conversation_hash, topic)
            watermark_count += 1
        except Exception as exc:
            # Log only the exception type — a message/traceback can embed model output.
            log.warning("Topic analysis failed for a turn (%s); counting as failed", type(exc).__name__)
            tally.add_failure()
            failed = True
        processed_turns += 1
        if processed_turns % config.PROGRESS_LOG_INTERVAL == 0:
            log.info(
                "Progress: conversations=%d processed_turns=%d failed_turns=%d",
                conversation_number,
                processed_turns,
                tally.failed_turns,
            )
        if failed:
            break
    return watermark_count, processed_turns


def _flush_batch(
    hana_conn: Any,
    schema: str,
    tally: TopicTally,
    watermarks: dict[str, tuple[int, str]],
    run_id: str,
    now: dt.datetime,
) -> None:
    """Checkpoint the assignments touched since the last flush plus their watermarks."""
    write_batch(
        hana_conn,
        schema,
        assignments=tally.drain_touched(),
        watermarks=watermarks,
        run_id=run_id,
        now=now,
    )


def _build_run_row(
    conn: Any, schema: str, tally: TopicTally, segmenter: Any, now: dt.datetime, run_id: str
) -> dict[str, Any]:
    return {
        "RUN_ID": run_id,
        "WINDOW_START": read_last_window_end(conn, schema),
        "WINDOW_END": now,
        "SEG_MODEL": config.SEG_MODEL_NAME,
        "PROMPT_TOKENS": segmenter.tokens["prompt_tokens"],
        "COMPLETION_TOKENS": segmenter.tokens["completion_tokens"],
        "TOTAL_TOKENS": segmenter.tokens["total_tokens"],
        "TURNS_ANALYZED": tally.total_turns,
        "FAILED_TURNS": tally.failed_turns,
        "TAXONOMY_VERSION": TAXONOMY_VERSION,
        "CREATED_AT": now,
    }


async def _segment_task() -> None:
    # Local imports: these pull in the app settings (loads config.json → env).
    from services.hana import get_hana  # noqa: PLC0415
    from services.redis import get_redis  # noqa: PLC0415
    from utils.config import get_config  # noqa: PLC0415
    from utils.models.factory import ModelFactory  # noqa: PLC0415
    from utils.settings import DATABASE_USER  # noqa: PLC0415

    # Importing the app services above triggers the app's logging setup, which honors the
    # mounted config's LOG_LEVEL (possibly DEBUG). Re-assert the job's log privacy now,
    # before any model/HTTP call could emit a request body.
    _enforce_log_privacy()

    model = ModelFactory(config=get_config()).create_model(config.SEG_MODEL_NAME)
    segmenter = Segmenter.build(model.llm)
    redis_conn = get_redis().get_connection()
    hana_conn = get_hana().get_connction()  # misspelling is in the app API
    try:
        await run_segmentation(
            redis_conn=redis_conn,
            hana_conn=hana_conn,
            segmenter=segmenter,
            schema=str(DATABASE_USER),
            now=dt.datetime.now(dt.UTC).replace(tzinfo=None),
        )
    finally:
        with contextlib.suppress(Exception):
            await redis_conn.aclose()


def main() -> None:
    """Parse CLI args and dispatch to the requested task."""
    parser = argparse.ArgumentParser(description="Kyma Companion conversation topic analysis.")
    parser.add_argument("task", choices=["segment"])
    args = parser.parse_args()
    if args.task == "segment":
        asyncio.run(_segment_task())


if __name__ == "__main__":
    main()
