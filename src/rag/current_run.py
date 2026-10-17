"""Lookup of the current index run of a corpus.

The kyma-docs-indexer writes every run into its own table ``<corpus>_<run_id>``
and records the runs in a run table (``DOCS_RUNS_TABLE``). Exactly one run per
corpus is current; readers ask the run table for its table instead of using a
fixed table name.

Each run has a ``schema_version`` ``MAJOR.MINOR`` (NULL, or no such column in an
older run table, means ``1.0``). A new MINOR only adds things, a new MAJOR breaks
readers. If the current run has a MAJOR this server does not support, it serves
the newest committed run of the corpus with a supported MAJOR instead.
"""

import re
import threading
import time
from collections.abc import Callable

from hdbcli import dbapi

from utils.logging import get_logger

logger = get_logger(__name__)

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")
_SCHEMA_VERSION = re.compile(r"^([0-9]+)\.([0-9]+)$")

SUPPORTED_SCHEMA_MAJORS = frozenset({1})
DEFAULT_SCHEMA_VERSION = "1.0"


class RunTableError(RuntimeError):
    """The run table has no usable run of the corpus: a state of the data, not a bug."""


class NoCurrentRunError(RunTableError):
    """Raised when the corpus has no current run in the run table."""


class InvalidRunTableError(RunTableError):
    """Raised when the run table points at a table name that is not a run table of the corpus."""


class UnsupportedSchemaError(RunTableError):
    """Raised when the current run has an unsupported schema and no older run is supported."""


class CurrentRunTableMissingError(RunTableError):
    """Raised when the table the run table points at does not exist, even after a new lookup."""


def schema_major(version: str | None) -> int | None:
    """MAJOR of a ``MAJOR.MINOR`` schema version; None means 1.0; None if unparseable."""
    if version is None:
        return 1
    match = _SCHEMA_VERSION.match(version.strip())
    return int(match.group(1)) if match else None


def _is_supported(version: str | None) -> bool:
    return schema_major(version) in SUPPORTED_SCHEMA_MAJORS


def _show(version: str | None) -> str:
    return DEFAULT_SCHEMA_VERSION if version is None else repr(version)


class CurrentRunTable:
    """Resolves the table of the current run of a corpus, cached for ``ttl_seconds``.

    ``resolve`` blocks on HANA; async callers run it in an executor. It is
    thread-safe: concurrent callers with an expired cache query only once.
    """

    def __init__(
        self,
        connection: dbapi.Connection,
        corpus: str,
        runs_table: str,
        ttl_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ):
        if not _IDENTIFIER.match(runs_table):
            raise ValueError(f"invalid run table name: {runs_table!r}")
        self.corpus = corpus
        self.runs_table = runs_table
        self._connection = connection
        self._ttl = ttl_seconds
        self._clock = clock
        # Only the prefix <corpus>_ is part of the indexer contract, not the rest of the name.
        # Lower case [a-z0-9_] only, and never the bare corpus (the legacy fixed table).
        prefix = re.sub(r"[^a-z0-9_]", "_", corpus.lower())
        self._valid_table = re.compile(rf"^{re.escape(prefix)}_[a-z0-9_]+$")
        self._lock = threading.Lock()
        self._table: str | None = None
        self._expires_at = 0.0
        # Columns are never dropped: once seen, the run table is not asked again.
        self._has_schema_version = False
        # Kept across invalidate, so a retry that finds the same table does not log again.
        self._logged_table: tuple[str, str] | None = None
        self._warned_fallback: tuple[str, str] | None = None

    def resolve(self) -> str:
        """Return the table of the current run, from the cache while it is fresh."""
        with self._lock:
            if self._table is None or self._clock() >= self._expires_at:
                self._table = self._query()
                self._expires_at = self._clock() + self._ttl
            return self._table

    def invalidate(self, stale: str) -> bool:
        """Forget the cached table if it is still ``stale``, so the next ``resolve`` asks again.

        Parallel searches that failed on the same dropped table must not wipe the
        table another search has resolved in the meantime. Returns True only for the
        caller that cleared the cache, so one dropped table is reported once.
        """
        with self._lock:
            if self._table != stale:
                return False
            self._table = None
            return True

    def _fetch(self, sql: str, params: tuple) -> list[tuple]:
        cursor = self._connection.cursor()
        try:
            cursor.execute(sql, params)
            return list(cursor.fetchall())
        finally:
            cursor.close()

    def _schema_version_column_exists(self) -> bool:
        if not self._has_schema_version:
            # The indexer quotes the run table name, not its columns (stored upper case).
            rows = self._fetch(
                "SELECT COUNT(*) FROM SYS.TABLE_COLUMNS WHERE SCHEMA_NAME = CURRENT_SCHEMA "
                "AND TABLE_NAME = ? AND COLUMN_NAME = 'SCHEMA_VERSION'",
                (self.runs_table,),
            )
            self._has_schema_version = bool(rows and rows[0][0])
        return self._has_schema_version

    def _query(self) -> str:
        version = "schema_version" if self._schema_version_column_exists() else "NULL"
        sql = (
            f"SELECT run_id, table_name, is_current, {version} "
            f'FROM "{self.runs_table}" '
            "WHERE corpus = ? AND (is_current = TRUE OR committed_at IS NOT NULL) "
            "ORDER BY committed_at DESC"
        )
        rows = self._fetch(sql, (self.corpus,))
        current = next((row for row in rows if row[2]), None)
        if current is None:
            raise NoCurrentRunError(f"corpus {self.corpus} has no current run in {self.runs_table}")
        run_id, table, _, schema = current
        fallback_note = ""
        if _is_supported(schema):
            self._warned_fallback = None
        else:
            fallback_note = f", fallback from current run {run_id} with schema_version {_show(schema)}"
            run_id, table, schema = self._fallback(rows, run_id, schema)
        table = str(table)
        # HanaDB puts the name into SQL, so only accept the run table names the indexer writes.
        if not self._valid_table.match(table):
            raise InvalidRunTableError(
                f"run {run_id} of corpus {self.corpus} in {self.runs_table} points at "
                f"{table!r}, which is not a run table of the corpus"
            )
        logged = (table, fallback_note)
        if logged != self._logged_table:
            what = "Serving run table" if fallback_note else "Current run table"
            logger.info(
                f"{what} of corpus {self.corpus}: {table} "
                f"(schema_version {schema or DEFAULT_SCHEMA_VERSION}{fallback_note})"
            )
            self._logged_table = logged
        return table

    def _fallback(self, rows: list[tuple], current_id: str, current_schema: str | None) -> tuple:
        """The newest committed, not current run with a supported schema; warns once per change."""
        older = next((row for row in rows if not row[2] and _is_supported(row[3])), None)
        unparseable = "" if schema_major(current_schema) is not None else " (unparseable)"
        if older is None:
            # Forget what was logged, so a recovery after this error is logged again.
            self._warned_fallback = None
            self._logged_table = None
            # The current run first, then the other kept (committed) runs, newest first.
            versions = [current_schema] + [row[3] for row in rows if not row[2]]
            found = ", ".join(dict.fromkeys(_show(v) for v in versions))
            raise UnsupportedSchemaError(
                f"corpus {self.corpus}: current run {current_id} has unsupported schema_version "
                f"{_show(current_schema)}{unparseable} and no kept run with a supported major "
                f"(schema_versions found: {found})"
            )
        run_id, table, _, schema = older
        if self._warned_fallback != (str(current_id), str(run_id)):
            majors = ", ".join(str(m) for m in sorted(SUPPORTED_SCHEMA_MAJORS))
            logger.warning(
                f"current run {current_id} of corpus {self.corpus} has schema_version "
                f"{_show(current_schema)}{unparseable}, this server supports major {majors}; "
                f"serving older run {run_id} (schema {schema or DEFAULT_SCHEMA_VERSION}). "
                "Update kyma-companion."
            )
            self._warned_fallback = (str(current_id), str(run_id))
        return run_id, table, schema
