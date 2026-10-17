"""Fakes of the run table and the vector store for the current run tests (no live HANA)."""

from __future__ import annotations

from hdbcli import dbapi
from langchain_core.documents import Document

from rag.current_run import CurrentRunTable
from rag.retriever import HanaDBRetriever, TableNotFoundError

RUN_A = "ops_docs_20261014093512_7be204"
RUN_B = "ops_docs_20261014120000_0a1b2c"


class FakeCursor:
    def __init__(self, conn: FakeConnection):
        self._conn = conn
        self._rows: list[tuple] = []

    def execute(self, sql: str, params: tuple) -> None:
        self._rows = self._conn.answer(sql, params)

    def fetchall(self) -> list[tuple]:
        return self._rows

    def close(self) -> None:
        pass


def run_id(table: str) -> str:
    return table.removeprefix("ops_docs_")


class FakeConnection:
    """Answers the run table query with ``current`` and the ``older`` committed runs.

    ``older`` lists (table, schema_version), newest first. Without ``has_column`` the run
    table has no schema_version column and must not be asked for it.
    """

    def __init__(
        self,
        current: str | None,
        schema_version: str | None = "1.0",
        older: list[tuple[str, str | None]] | None = None,
        has_column: bool = True,
    ):
        self.current = current
        self.schema_version = schema_version
        self.older = older or []
        self.has_column = has_column
        self.queries: list[tuple[str, tuple]] = []
        self.column_checks = 0

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def answer(self, sql: str, params: tuple) -> list[tuple]:
        if "TABLE_COLUMNS" in sql:
            self.column_checks += 1
            assert params == ("docs_index_runs",)
            return [(1 if self.has_column else 0,)]
        self.queries.append((sql, params))
        assert ("schema_version" in sql) == self.has_column
        runs = [(t, v, False) for t, v in self.older]
        if self.current:
            runs.insert(0, (self.current, self.schema_version, True))
        return [(run_id(t), t, cur, v if self.has_column else None) for t, v, cur in runs]


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def make_lookup(conn: FakeConnection, clock: FakeClock | None = None) -> CurrentRunTable:
    return CurrentRunTable(
        conn,  # type: ignore[arg-type]
        corpus="ops_docs",
        runs_table="docs_index_runs",
        ttl_seconds=60,
        clock=clock or FakeClock(),
    )


class FakeVectorDB:
    """Stands in for HanaVectorDB; ``missing`` lists dropped tables."""

    missing: set[str] = set()
    created: list[str] = []

    def __init__(self, connection, embedding, table_name: str):
        if table_name in FakeVectorDB.missing:
            raise TableNotFoundError(f"table {table_name} does not exist")
        self.table_name = table_name
        FakeVectorDB.created.append(table_name)

    def similarity_search(self, query: str, k: int = 4) -> list[Document]:
        if self.table_name in FakeVectorDB.missing:
            raise dbapi.ProgrammingError(259, f"invalid table name: {self.table_name}")
        return [Document(page_content=f"{self.table_name}:{query}")]


def make_retriever(conn: FakeConnection, clock: FakeClock) -> HanaDBRetriever:
    return HanaDBRetriever(
        embedding=None,  # type: ignore[arg-type]
        connection=conn,  # type: ignore[arg-type]
        current_run=make_lookup(conn, clock),
    )
