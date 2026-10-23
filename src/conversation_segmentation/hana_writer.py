"""HANA persistence: create tables if absent, read/prune watermarks, and write one
run atomically (aggregate row + watermark upserts + prune in a single transaction).

Table existence is checked via M_TABLES (the doc_indexer convention) rather than
relying on CREATE TABLE IF NOT EXISTS. Tables are schema-qualified with the
connecting DATABASE_USER. Values use `?` placeholders (HANA style).
"""

import datetime as dt
import logging
from typing import Any

from conversation_segmentation import config
from conversation_segmentation.taxonomy import crosstab_columns

log = logging.getLogger(__name__)

_META_COLUMNS = [
    "RUN_ID BIGINT",
    "WINDOW_START TIMESTAMP",
    "WINDOW_END TIMESTAMP",
    "LANDSCAPE NVARCHAR(64)",
    "TOTAL_TURNS INTEGER",
    "FAILED_TURNS INTEGER",
    "SEG_MODEL NVARCHAR(128)",
    "PROMPT_TOKENS BIGINT",
    "COMPLETION_TOKENS BIGINT",
    "TOTAL_TOKENS BIGINT",
    "CREATED_AT TIMESTAMP",
]


def _agg_ddl(schema: str) -> str:
    cell_defs = ", ".join(f"{c} INTEGER" for c in crosstab_columns())
    meta_defs = ", ".join(_META_COLUMNS)
    return f'CREATE TABLE "{schema}"."{config.AGG_TABLE}" ({meta_defs}, {cell_defs})'


def _watermark_ddl(schema: str) -> str:
    return (
        f'CREATE TABLE "{schema}"."{config.WATERMARK_TABLE}" '
        f"(SESSION_KEY NVARCHAR(64) PRIMARY KEY, TURNS_SEGMENTED INTEGER, "
        f"HEAD_FINGERPRINT NVARCHAR(64), UPDATED_AT TIMESTAMP)"
    )


def table_exists(conn: Any, schema: str, table: str) -> bool:
    """Check if a table exists by querying M_TABLES."""
    sql = "SELECT COUNT(*) FROM M_TABLES WHERE SCHEMA_NAME = ? AND TABLE_NAME = ?"
    with conn.cursor() as cur:
        cur.execute(sql, (schema, table))
        row = cur.fetchone()
        return (row[0] if row else 0) > 0


def ensure_tables(conn: Any, schema: str) -> None:
    """Create tables if absent, commit once after all DDL."""
    if not table_exists(conn, schema, config.AGG_TABLE):
        with conn.cursor() as cur:
            cur.execute(_agg_ddl(schema))
        log.info("Created aggregate table %s.%s", schema, config.AGG_TABLE)
    if not table_exists(conn, schema, config.WATERMARK_TABLE):
        with conn.cursor() as cur:
            cur.execute(_watermark_ddl(schema))
        log.info("Created watermark table %s.%s", schema, config.WATERMARK_TABLE)
    conn.commit()


def read_watermarks(conn: Any, schema: str) -> dict[str, tuple[int, str]]:
    """Read all session watermarks (key → (turns_segmented, head_fingerprint)) from the watermark table."""
    with conn.cursor() as cur:
        cur.execute(f'SELECT SESSION_KEY, TURNS_SEGMENTED, HEAD_FINGERPRINT FROM "{schema}"."{config.WATERMARK_TABLE}"')
        return {row[0]: (row[1], row[2] if row[2] is not None else "") for row in cur.fetchall()}


def write_run(
    conn: Any, schema: str, agg_row: dict, watermarks: dict[str, tuple[int, str]], prune_before: dt.datetime
) -> None:
    """Atomically: INSERT the aggregate row, UPSERT all watermarks, DELETE stale ones.

    hdbcli connections default to autocommit=True, which would commit each statement
    on its own; disable it so a mid-write failure rolls back the whole run (otherwise a
    committed aggregate row with un-advanced watermarks would double-count next run).
    Restored afterwards since the connection is a process-wide singleton.
    """
    cols = list(agg_row.keys())
    now = dt.datetime.now(dt.UTC)
    conn.setautocommit(False)
    try:
        with conn.cursor() as cur:
            placeholders = ", ".join("?" for _ in cols)
            insert_sql = f'INSERT INTO "{schema}"."{config.AGG_TABLE}" ({", ".join(cols)}) VALUES ({placeholders})'
            cur.execute(insert_sql, tuple(agg_row[c] for c in cols))

            upsert_sql = (
                f'UPSERT "{schema}"."{config.WATERMARK_TABLE}" '
                f"(SESSION_KEY, TURNS_SEGMENTED, HEAD_FINGERPRINT, UPDATED_AT) VALUES (?, ?, ?, ?) WITH PRIMARY KEY"
            )
            for key, value in watermarks.items():
                count, fp = value
                cur.execute(upsert_sql, (key, count, fp, now))

            cur.execute(f'DELETE FROM "{schema}"."{config.WATERMARK_TABLE}" WHERE UPDATED_AT < ?', (prune_before,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.setautocommit(True)
