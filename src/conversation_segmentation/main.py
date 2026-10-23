"""Entrypoint for the conversation-segmentation CronJob.

Run in the Companion image as:  python3.14 -m conversation_segmentation.main segment
"""

import argparse
import asyncio
import datetime as dt
import logging
from typing import Any

from conversation_segmentation import config
from conversation_segmentation.aggregator import Crosstab
from conversation_segmentation.hana_writer import ensure_tables, read_watermarks, write_run
from conversation_segmentation.redis_reader import pair_turns, parse_messages, scan_conversations
from conversation_segmentation.segmenter import Segmenter
from conversation_segmentation.watermark import head_fingerprint, select_new_turns, session_key

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("conversation_segmentation")


async def run_segmentation(
    *, redis_conn: Any, hana_conn: Any, segmenter: Any, schema: str, landscape: str, now: dt.datetime
) -> dict[str, Any]:
    """Segment only-new turns for every live conversation and write one aggregate row."""
    ensure_tables(hana_conn, schema)
    prior = read_watermarks(hana_conn, schema)
    ct = Crosstab()
    new_watermarks: dict[str, tuple[int, str]] = {}

    conversations = await scan_conversations(redis_conn, config.CONVERSATION_KEY_PREFIX)
    for session_id, raw_json in conversations:
        turns = pair_turns(parse_messages(raw_json))
        key = session_key(session_id)
        cur_fp = head_fingerprint(turns)
        prior_count, prior_fp = prior.get(key, (0, ""))
        already = prior_count if cur_fp == prior_fp else 0  # fp mismatch → reused id → re-segment all
        for turn in select_new_turns(turns, already):
            try:
                category, judgement = await segmenter.segment_turn(turn["query"], turn["response"])
                ct.add(category, judgement)
            except Exception:  # skip-and-count: never let one turn abort the run
                log.exception("Segmentation failed for a turn; counting as failed")
                ct.add_failure()
        if turns or prior_count == 0:
            new_watermarks[key] = (len(turns), cur_fp)  # advance regardless of per-turn failures
        # else: empty parse (transient malformed JSON) with a valid prior — keep it, don't clobber to (0, "")

    prior_end = _last_window_end(hana_conn, schema)
    agg_row: dict[str, Any] = {
        "RUN_ID": int(now.timestamp()),
        "WINDOW_START": prior_end,
        "WINDOW_END": now,
        "LANDSCAPE": landscape,
        "TOTAL_TURNS": ct.total_turns,
        "FAILED_TURNS": ct.failed_turns,
        "SEG_MODEL": config.SEG_MODEL_NAME,
        "PROMPT_TOKENS": segmenter.tokens["prompt_tokens"],
        "COMPLETION_TOKENS": segmenter.tokens["completion_tokens"],
        "TOTAL_TOKENS": segmenter.tokens["total_tokens"],
        "CREATED_AT": now,
        **ct.cells(),
    }
    prune_before = now - dt.timedelta(seconds=config.WATERMARK_TTL_SECONDS)
    write_run(hana_conn, schema, agg_row, new_watermarks, prune_before)
    log.info(
        "Wrote run: total=%d failed=%d sessions=%d",
        ct.total_turns,
        ct.failed_turns,
        len(new_watermarks),
    )
    return agg_row


def _last_window_end(conn: Any, schema: str) -> dt.datetime | None:
    """Query HANA for the MAX(CREATED_AT) of the previous run; None on first run."""
    with conn.cursor() as cur:
        cur.execute(f'SELECT MAX(CREATED_AT) FROM "{schema}"."{config.AGG_TABLE}"')
        row = cur.fetchone()
        return row[0] if row else None


async def _segment_task() -> None:
    # Local imports: these pull in the app settings (loads config.json → env).
    from services.hana import get_hana  # noqa: PLC0415
    from services.redis import get_redis  # noqa: PLC0415
    from utils.config import get_config  # noqa: PLC0415
    from utils.models.factory import ModelFactory  # noqa: PLC0415
    from utils.settings import DATABASE_USER  # noqa: PLC0415

    model = ModelFactory(config=get_config()).create_model(config.SEG_MODEL_NAME)
    segmenter = Segmenter.build(model.llm)
    redis_conn = get_redis().get_connection()
    hana_conn = get_hana().get_connction()  # misspelling is in the app API
    await run_segmentation(
        redis_conn=redis_conn,
        hana_conn=hana_conn,
        segmenter=segmenter,
        schema=str(DATABASE_USER),
        landscape=config.LANDSCAPE,
        now=dt.datetime.now(dt.UTC).replace(tzinfo=None),
    )


def main() -> None:
    """Parse CLI args and dispatch to the requested task."""
    parser = argparse.ArgumentParser(description="Kyma Companion conversation segmentation.")
    parser.add_argument("task", choices=["segment"])
    args = parser.parse_args()
    if args.task == "segment":
        asyncio.run(_segment_task())


if __name__ == "__main__":
    main()
