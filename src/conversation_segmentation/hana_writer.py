"""HANA persistence for dynamic topic analysis.

Four tables (created if absent, schema-qualified with the connecting DATABASE_USER):

* ``CONVERSATION_ANALYSIS_RUN``   — one row per completed run (history, tokens, counts).
* ``CONVERSATION_TOPIC_ASSIGNMENT`` — durable, one row per (conversation_hash, topic_key)
  with a cumulative turn count. Primary-keyed; upserted incrementally.
* ``CONVERSATION_TOPIC_AGGREGATE`` — cumulative reporting snapshot, replaced every run.

A ``CONVERSATION_TOPIC_WATERMARK`` table records, per conversation, how many turns have
already been analysed so later runs skip them. Progress is checkpointed in batches:
``write_batch`` upserts each batch of touched assignments and watermarks in its own
transaction, so a crash loses at most one batch and a re-run resumes from the committed
watermarks. ``write_run`` then finalizes the run in one transaction — inserting the run
row and replacing the derived aggregate snapshot — so a partial snapshot is never visible.

Complete raw conversation text, raw session IDs, and model reasoning are not directly stored.
Only a one-way conversation-instance hash and best-effort-scrubbed derived text are persisted.
"""

import datetime as dt
import logging
import re
from typing import Any

from conversation_segmentation import config
from conversation_segmentation.aggregator import AssignmentState, TaxonomyVersionMismatchError
from conversation_segmentation.taxonomy import TAXONOMY_VERSION

log = logging.getLogger(__name__)

_SUMMARY_SEPARATOR = " | "

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")


def _validate_identifier(name: str) -> str:
    """Guard a schema/table name used in SQL (identifiers cannot be bound as params)."""
    if not _IDENTIFIER.match(name):
        raise ValueError(f"Unsafe SQL identifier: {name!r}")
    return name


def _qualified_table(schema: str, table: str) -> str:
    """Return a quoted table name after validating both interpolated identifiers."""
    return f'"{_validate_identifier(schema)}"."{_validate_identifier(table)}"'


_RUN_DDL_COLUMNS = (
    "RUN_ID NVARCHAR(32) PRIMARY KEY, WINDOW_START TIMESTAMP, WINDOW_END TIMESTAMP, "
    "SEG_MODEL NVARCHAR(128), PROMPT_TOKENS BIGINT, COMPLETION_TOKENS BIGINT, TOTAL_TOKENS BIGINT, "
    "TURNS_ANALYZED INTEGER, FAILED_TURNS INTEGER, TAXONOMY_VERSION NVARCHAR(32), CREATED_AT TIMESTAMP"
)
_RUN_COLUMNS = frozenset(
    {
        "RUN_ID",
        "WINDOW_START",
        "WINDOW_END",
        "SEG_MODEL",
        "PROMPT_TOKENS",
        "COMPLETION_TOKENS",
        "TOTAL_TOKENS",
        "TURNS_ANALYZED",
        "FAILED_TURNS",
        "TAXONOMY_VERSION",
        "CREATED_AT",
    }
)

_ASSIGNMENT_DDL_COLUMNS = (
    "CONVERSATION_HASH NVARCHAR(64), TOPIC_KEY NVARCHAR(256), AREA NVARCHAR(64), INTENT NVARCHAR(64), "
    "CAPABILITY NVARCHAR(128), TOPIC_LABEL NVARCHAR(256), SUMMARY NVARCHAR(256), CONFIDENCE DECIMAL(5,4), "
    "TURN_COUNT INTEGER, TAXONOMY_VERSION NVARCHAR(32), RUN_ID NVARCHAR(32), UPDATED_AT TIMESTAMP, "
    "PRIMARY KEY (CONVERSATION_HASH, TOPIC_KEY)"
)
_ASSIGNMENT_COLUMNS = frozenset(
    {
        "CONVERSATION_HASH",
        "TOPIC_KEY",
        "AREA",
        "INTENT",
        "CAPABILITY",
        "TOPIC_LABEL",
        "SUMMARY",
        "CONFIDENCE",
        "TURN_COUNT",
        "TAXONOMY_VERSION",
        "RUN_ID",
        "UPDATED_AT",
    }
)

_AGGREGATE_DDL_COLUMNS = (
    "TOPIC_KEY NVARCHAR(256), AREA NVARCHAR(64), INTENT NVARCHAR(64), CAPABILITY NVARCHAR(128), "
    "TOPIC_LABEL NVARCHAR(256), DISTINCT_CONVERSATION_COUNT INTEGER, TURN_COUNT INTEGER, "
    "EXAMPLE_SUMMARIES NVARCHAR(1000), TAXONOMY_VERSION NVARCHAR(32), "
    "RUN_ID NVARCHAR(32), COMPUTED_AT TIMESTAMP, PRIMARY KEY (TOPIC_KEY)"
)
_AGGREGATE_COLUMNS = frozenset(
    {
        "TOPIC_KEY",
        "AREA",
        "INTENT",
        "CAPABILITY",
        "TOPIC_LABEL",
        "DISTINCT_CONVERSATION_COUNT",
        "TURN_COUNT",
        "EXAMPLE_SUMMARIES",
        "TAXONOMY_VERSION",
        "RUN_ID",
        "COMPUTED_AT",
    }
)

_WATERMARK_DDL_COLUMNS = (
    "SESSION_KEY NVARCHAR(64) PRIMARY KEY, TURNS_SEGMENTED INTEGER, HEAD_FINGERPRINT NVARCHAR(64), UPDATED_AT TIMESTAMP"
)
_WATERMARK_COLUMNS = frozenset({"SESSION_KEY", "TURNS_SEGMENTED", "HEAD_FINGERPRINT", "UPDATED_AT"})


def table_exists(conn: Any, schema: str, table: str) -> bool:
    """Check if a table exists by querying M_TABLES."""
    sql = "SELECT COUNT(*) FROM M_TABLES WHERE SCHEMA_NAME = ? AND TABLE_NAME = ?"
    with conn.cursor() as cur:
        cur.execute(sql, (schema, table))
        row = cur.fetchone()
        return (row[0] if row else 0) > 0


def _validate_table_columns(conn: Any, schema: str, table: str, expected: frozenset[str]) -> None:
    """Fail fast when an existing table does not match the code's required schema."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COLUMN_NAME FROM TABLE_COLUMNS WHERE SCHEMA_NAME = ? AND TABLE_NAME = ?",
            (schema, table),
        )
        actual = {str(row[0]) for row in cur.fetchall()}
    missing = expected - actual
    if missing:
        raise RuntimeError(f"Table {schema}.{table} is missing required columns: {', '.join(sorted(missing))}")


def _create_or_validate(conn: Any, schema: str, table: str, columns: str, expected: frozenset[str]) -> None:
    if table_exists(conn, schema, table):
        _validate_table_columns(conn, schema, table, expected)
        return
    with conn.cursor() as cur:
        cur.execute(f"CREATE TABLE {_qualified_table(schema, table)} ({columns})")
    log.info("Created table %s.%s", schema, table)


def ensure_tables(conn: Any, schema: str) -> None:
    """Create the four tables if absent, commit once after all DDL."""
    _validate_identifier(schema)
    for table in (config.RUN_TABLE, config.ASSIGNMENT_TABLE, config.AGGREGATE_TABLE, config.WATERMARK_TABLE):
        _validate_identifier(table)
    _create_or_validate(conn, schema, config.RUN_TABLE, _RUN_DDL_COLUMNS, _RUN_COLUMNS)
    _create_or_validate(conn, schema, config.ASSIGNMENT_TABLE, _ASSIGNMENT_DDL_COLUMNS, _ASSIGNMENT_COLUMNS)
    _create_or_validate(conn, schema, config.AGGREGATE_TABLE, _AGGREGATE_DDL_COLUMNS, _AGGREGATE_COLUMNS)
    _create_or_validate(conn, schema, config.WATERMARK_TABLE, _WATERMARK_DDL_COLUMNS, _WATERMARK_COLUMNS)
    conn.commit()


def read_last_window_end(conn: Any, schema: str) -> dt.datetime | None:
    """Return MAX(CREATED_AT) of the previous run, or None on the first run."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT MAX(CREATED_AT) FROM {_qualified_table(schema, config.RUN_TABLE)}")
        row = cur.fetchone()
        return row[0] if row else None


def validate_taxonomy_version(conn: Any, schema: str) -> None:
    """Fail before processing when persisted runs require an explicit taxonomy migration."""
    with conn.cursor() as cur:
        cur.execute(f"SELECT DISTINCT TAXONOMY_VERSION FROM {_qualified_table(schema, config.RUN_TABLE)}")
        versions = {str(row[0]) for row in cur.fetchall() if row[0] is not None}
    stale_versions = versions - {TAXONOMY_VERSION}
    if stale_versions:
        persisted = ", ".join(sorted(stale_versions))
        raise TaxonomyVersionMismatchError(
            f"Persisted run taxonomy ({persisted}) does not match current taxonomy ({TAXONOMY_VERSION})"
        )


def read_watermarks(conn: Any, schema: str) -> dict[str, tuple[int, str]]:
    """Read all session watermarks (key → (turns_segmented, head_fingerprint))."""
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT SESSION_KEY, TURNS_SEGMENTED, HEAD_FINGERPRINT "
            f"FROM {_qualified_table(schema, config.WATERMARK_TABLE)}"
        )
        return {row[0]: (row[1], row[2] if row[2] is not None else "") for row in cur.fetchall()}


def read_assignments(conn: Any, schema: str) -> list[AssignmentState]:
    """Read all stored topic assignments so cumulative counts survive across runs."""
    sql = (
        "SELECT CONVERSATION_HASH, TOPIC_KEY, AREA, INTENT, CAPABILITY, TOPIC_LABEL, SUMMARY, "
        f"CONFIDENCE, TURN_COUNT, TAXONOMY_VERSION FROM {_qualified_table(schema, config.ASSIGNMENT_TABLE)}"
    )
    with conn.cursor() as cur:
        cur.execute(sql)
        return [
            AssignmentState(
                conversation_hash=row[0],
                topic_key=row[1],
                area=row[2],
                intent=row[3],
                capability=row[4],
                label=row[5] or "",
                summary=row[6] or "",
                confidence=float(row[7]) if row[7] is not None else 0.0,
                turn_count=int(row[8]) if row[8] is not None else 0,
                taxonomy_version=row[9] if row[9] is not None else TAXONOMY_VERSION,
            )
            for row in cur.fetchall()
        ]


def write_batch(
    conn: Any,
    schema: str,
    *,
    assignments: list[AssignmentState],
    watermarks: dict[str, tuple[int, str]],
    run_id: str,
    now: dt.datetime,
) -> None:
    """Atomically persist one batch of touched assignments plus their watermarks.

    Called repeatedly during a run so progress is durable and resumable: a crash
    loses at most the in-flight batch, and a re-run continues from the committed
    watermarks. Each batch is its own transaction. A no-op when nothing changed.

    hdbcli connections default to autocommit=True; disable it so a mid-batch failure
    rolls back the batch, then restore it (the connection is a singleton).
    """
    if not assignments and not watermarks:
        return
    conn.setautocommit(False)
    try:
        with conn.cursor() as cur:
            _upsert_assignments(cur, schema, assignments, run_id, now)
            _upsert_watermarks(cur, schema, watermarks, now)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.setautocommit(True)


def write_run(
    conn: Any,
    schema: str,
    *,
    run_row: dict,
    aggregate_rows: list[dict],
    now: dt.datetime,
) -> None:
    """Atomically insert the run row and replace the cumulative aggregate snapshot.

    Assignments and watermarks are already durable from per-batch ``write_batch``
    calls. The aggregate is a derived cumulative snapshot, rebuilt here in one
    transaction so a partial snapshot is never visible.

    hdbcli connections default to autocommit=True; disable it so a mid-write failure
    rolls back, then restore it (the connection is a singleton).
    """
    conn.setautocommit(False)
    try:
        with conn.cursor() as cur:
            _insert_run(cur, schema, run_row)
            _replace_aggregate(cur, schema, aggregate_rows, run_row["RUN_ID"], now)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.setautocommit(True)


def _insert_run(cur: Any, schema: str, run_row: dict) -> None:
    cols = list(run_row.keys())
    placeholders = ", ".join("?" for _ in cols)
    cur.execute(
        f"INSERT INTO {_qualified_table(schema, config.RUN_TABLE)} ({', '.join(cols)}) VALUES ({placeholders})",
        tuple(run_row[c] for c in cols),
    )


def _upsert_assignments(
    cur: Any, schema: str, assignments: list[AssignmentState], run_id: str, now: dt.datetime
) -> None:
    sql = (
        f"UPSERT {_qualified_table(schema, config.ASSIGNMENT_TABLE)} "
        "(CONVERSATION_HASH, TOPIC_KEY, AREA, INTENT, CAPABILITY, TOPIC_LABEL, SUMMARY, CONFIDENCE, "
        "TURN_COUNT, TAXONOMY_VERSION, RUN_ID, UPDATED_AT) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "WITH PRIMARY KEY"
    )
    if assignments:
        cur.executemany(
            sql,
            [
                (
                    a.conversation_hash,
                    a.topic_key,
                    a.area,
                    a.intent,
                    a.capability,
                    a.label,
                    a.summary,
                    a.confidence,
                    a.turn_count,
                    a.taxonomy_version,
                    run_id,
                    now,
                )
                for a in assignments
            ],
        )


def _replace_aggregate(cur: Any, schema: str, rows: list[dict], run_id: str, now: dt.datetime) -> None:
    """The aggregate is a cumulative snapshot: clear it, then insert fresh rows."""
    cur.execute(f"DELETE FROM {_qualified_table(schema, config.AGGREGATE_TABLE)}")
    sql = (
        f"INSERT INTO {_qualified_table(schema, config.AGGREGATE_TABLE)} "
        "(TOPIC_KEY, AREA, INTENT, CAPABILITY, TOPIC_LABEL, DISTINCT_CONVERSATION_COUNT, TURN_COUNT, "
        "EXAMPLE_SUMMARIES, TAXONOMY_VERSION, RUN_ID, COMPUTED_AT) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )
    if rows:
        cur.executemany(
            sql,
            [
                (
                    r["TOPIC_KEY"],
                    r["AREA"],
                    r["INTENT"],
                    r["CAPABILITY"],
                    r["TOPIC_LABEL"],
                    r["DISTINCT_CONVERSATION_COUNT"],
                    r["TURN_COUNT"],
                    _SUMMARY_SEPARATOR.join(r["EXAMPLE_SUMMARIES"])[:1000],
                    r["TAXONOMY_VERSION"],
                    run_id,
                    now,
                )
                for r in rows
            ],
        )


def _upsert_watermarks(cur: Any, schema: str, watermarks: dict[str, tuple[int, str]], now: dt.datetime) -> None:
    sql = (
        f"UPSERT {_qualified_table(schema, config.WATERMARK_TABLE)} "
        "(SESSION_KEY, TURNS_SEGMENTED, HEAD_FINGERPRINT, UPDATED_AT) VALUES (?, ?, ?, ?) WITH PRIMARY KEY"
    )
    if watermarks:
        cur.executemany(
            sql,
            [(key, count, fingerprint, now) for key, (count, fingerprint) in watermarks.items()],
        )
