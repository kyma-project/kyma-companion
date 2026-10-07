import json
import re

import psycopg
from langchain_core.documents import Document
from writers.base import RunDescriptor

from utils.logging import get_logger

logger = get_logger(__name__)

KEEP_COMMITTED_RUNS = 2
_RUN_ID_RE = re.compile(r"^[a-z0-9_]+$")

_CREATE_RUNS_SQL = """
CREATE TABLE IF NOT EXISTS docs_index_runs (
  run_id          text PRIMARY KEY,
  table_name      text NOT NULL,
  embedding_model text NOT NULL,
  dimensions      integer NOT NULL,
  chunk_count     integer NOT NULL DEFAULT 0,
  sources         jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at      timestamptz NOT NULL DEFAULT now(),
  committed_at    timestamptz,
  is_current      boolean NOT NULL DEFAULT false
)
"""
_CREATE_ONE_CURRENT_SQL = (
    "CREATE UNIQUE INDEX IF NOT EXISTS docs_index_runs_one_current ON docs_index_runs (is_current) WHERE is_current"
)


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


class PgVectorWriter:
    """Writes one run into its own table docs_chunks_<run_id>; commit flips the is_current pointer."""

    needs_embeddings = True

    def __init__(self, dsn: str):
        self.dsn = dsn
        self._conn: psycopg.Connection | None = None
        self._run: RunDescriptor | None = None
        self._table: str = ""
        self._count = 0

    def begin(self, run: RunDescriptor) -> None:
        """Prepare the output for a new run."""
        if not _RUN_ID_RE.match(run.run_id):
            raise ValueError(f"invalid run_id: {run.run_id}")
        self._run = run
        self._table = f"docs_chunks_{run.run_id}"
        self._count = 0
        self._conn = psycopg.connect(self.dsn)
        with self._conn.transaction():
            self._conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            self._conn.execute(_CREATE_RUNS_SQL)
            self._conn.execute(_CREATE_ONE_CURRENT_SQL)
            self._conn.execute(
                "INSERT INTO docs_index_runs (run_id, table_name, embedding_model, dimensions, sources, is_current) "
                "VALUES (%s, %s, %s, %s, %s, false)",
                (run.run_id, self._table, run.embedding_model, run.dimensions, json.dumps(run.sources)),
            )
            self._conn.execute(
                f"CREATE TABLE {self._table} (id bigserial PRIMARY KEY, content text NOT NULL, "
                f"metadata jsonb NOT NULL, embedding vector({int(run.dimensions)}) NOT NULL)"
            )

    def write(self, chunks: list[Document], vectors: list[list[float]]) -> None:
        """Write one batch of chunks (with vectors if the writer needs them)."""
        assert self._conn is not None
        rows = [
            (c.page_content, json.dumps(c.metadata), _vector_literal(v)) for c, v in zip(chunks, vectors, strict=True)
        ]
        with self._conn.transaction(), self._conn.cursor() as cur:
            cur.executemany(
                f"INSERT INTO {self._table} (content, metadata, embedding) VALUES (%s, %s::jsonb, %s::vector)",
                rows,
            )
        self._count += len(rows)

    def commit(self) -> None:
        """Make the written run visible."""
        assert self._conn is not None and self._run is not None
        with self._conn.transaction():
            self._conn.execute("UPDATE docs_index_runs SET is_current = false WHERE is_current")
            self._conn.execute(
                "UPDATE docs_index_runs SET is_current = true, committed_at = now(), chunk_count = %s "
                "WHERE run_id = %s",
                (self._count, self._run.run_id),
            )
        self._cleanup_old_runs()
        logger.info(f"Committed run {self._run.run_id} with {self._count} chunks in table {self._table}")
        self._close()

    def _cleanup_old_runs(self) -> None:
        assert self._conn is not None
        with self._conn.transaction():
            rows = self._conn.execute(
                "SELECT run_id, table_name FROM docs_index_runs "
                "WHERE NOT is_current AND (committed_at IS NULL OR run_id NOT IN ("
                "  SELECT run_id FROM docs_index_runs WHERE committed_at IS NOT NULL "
                "  ORDER BY committed_at DESC LIMIT %s)) "
                "AND run_id <> %s",
                (KEEP_COMMITTED_RUNS, self._run.run_id if self._run else ""),
            ).fetchall()
            for run_id, table_name in rows:
                if not _RUN_ID_RE.match(table_name):
                    continue
                self._conn.execute(f"DROP TABLE IF EXISTS {table_name}")
                self._conn.execute("DELETE FROM docs_index_runs WHERE run_id = %s", (run_id,))
                logger.info(f"Dropped old run {run_id}")

    def abort(self) -> None:
        """Discard everything written by this run."""
        if self._conn is None or self._run is None:
            return
        try:
            self._conn.rollback()
            with self._conn.transaction():
                self._conn.execute(f"DROP TABLE IF EXISTS {self._table}")
                self._conn.execute("DELETE FROM docs_index_runs WHERE run_id = %s", (self._run.run_id,))
        except Exception:
            logger.exception("Error while aborting pgvector run")
        finally:
            self._close()

    def _close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
