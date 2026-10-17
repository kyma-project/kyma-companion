"""Tests for the retriever over the table of the current run (no live HANA)."""

import logging
import threading

import pytest
from hdbcli import dbapi

import rag.retriever as retriever_module
from rag.current_run import CurrentRunTableMissingError, NoCurrentRunError
from rag.retriever import TableNotFoundError
from services.metrics import HANADB_LATENCY_METRIC_KEY, CustomMetrics
from unit.rag.fakes import RUN_A, RUN_B, FakeClock, FakeConnection, FakeVectorDB, make_retriever

# Two lookups (or log lines, or warnings): the first one and the one after a change.
TWICE = 2


@pytest.mark.asyncio
async def test_retriever_reuses_db_and_rebuilds_on_new_run(fake_db):
    conn, clock = FakeConnection(RUN_A), FakeClock()
    retriever = make_retriever(conn, clock)

    assert (await retriever.aretrieve("q"))[0].page_content == f"{RUN_A}:q"
    await retriever.aretrieve("q")
    assert fake_db.created == [RUN_A]

    conn.current = RUN_B
    clock.now = 61
    assert (await retriever.aretrieve("q"))[0].page_content == f"{RUN_B}:q"
    assert fake_db.created == [RUN_A, RUN_B]


@pytest.mark.asyncio
async def test_retriever_retries_once_on_dropped_table(fake_db):
    conn, clock = FakeConnection(RUN_A), FakeClock()
    retriever = make_retriever(conn, clock)
    await retriever.aretrieve("q")

    # The pointer flipped and the old table was dropped, all within the TTL.
    conn.current = RUN_B
    fake_db.missing = {RUN_A}

    assert (await retriever.aretrieve("q"))[0].page_content == f"{RUN_B}:q"
    assert len(conn.queries) == TWICE


@pytest.mark.asyncio
async def test_retriever_retries_when_table_is_gone_before_build(fake_db):
    conn, clock = FakeConnection(RUN_A), FakeClock()
    retriever = make_retriever(conn, clock)
    fake_db.missing = {RUN_A}
    retriever.current_run.resolve()  # cached before the flip
    conn.current = RUN_B

    assert (await retriever.aretrieve("q"))[0].page_content == f"{RUN_B}:q"
    assert fake_db.created == [RUN_B]


def test_concurrent_retries_resolve_once(fake_db, caplog):
    conn, clock = FakeConnection(RUN_A), FakeClock()
    retriever = make_retriever(conn, clock)
    retriever.current_run.resolve()
    conn.current = RUN_B
    fake_db.missing = {RUN_A}
    # All searches use the cached old table before any of them retries.
    barrier = threading.Barrier(5)
    resolve = retriever.current_run.resolve

    def resolve_together() -> str:
        table = resolve()
        if table == RUN_A:
            barrier.wait(timeout=5)
        return table

    retriever.current_run.resolve = resolve_together  # type: ignore[method-assign]
    results: list[str] = []

    def search() -> None:
        results.append(retriever._search("q", 5)[0].page_content)

    threads = [threading.Thread(target=search) for _ in range(5)]
    with caplog.at_level(logging.DEBUG, logger="rag.retriever"):
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert results == [f"{RUN_B}:q"] * 5
    assert len(conn.queries) == TWICE
    # One dropped table, one warning: not one per parallel search.
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    expected = f"Table {RUN_A} of the current run of corpus ops_docs is gone"
    assert expected in warnings[0].getMessage()


@pytest.mark.asyncio
async def test_retriever_retries_only_once(fake_db, caplog):
    conn, clock = FakeConnection(RUN_A), FakeClock()
    retriever = make_retriever(conn, clock)
    fake_db.missing = {RUN_A}

    with (
        caplog.at_level(logging.INFO),
        pytest.raises(
            CurrentRunTableMissingError,
            match=(f"the run table docs_index_runs of corpus ops_docs points at table {RUN_A}, which does not exist"),
        ),
    ):
        await retriever.aretrieve("q")
    assert len(conn.queries) == TWICE
    # A state of the run table: logged once as an error, without traceback.
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert errors[0].exc_info is None
    assert "does not exist" in errors[0].getMessage()


@pytest.mark.asyncio
async def test_retriever_reports_missing_table_after_retry_from_similarity_search(fake_db):
    conn, clock = FakeConnection(RUN_A), FakeClock()
    retriever = make_retriever(conn, clock)
    await retriever.aretrieve("q")  # the vector store exists, then the table is dropped
    fake_db.missing = {RUN_A}

    with pytest.raises(CurrentRunTableMissingError):
        await retriever.aretrieve("q")


@pytest.mark.asyncio
async def test_retriever_does_not_retry_other_errors(fake_db, monkeypatch):
    conn, clock = FakeConnection(RUN_A), FakeClock()
    retriever = make_retriever(conn, clock)

    def fail(self, query, k=4):
        raise dbapi.Error(10, "authentication failed")

    monkeypatch.setattr(FakeVectorDB, "similarity_search", fail)
    with pytest.raises(dbapi.Error):
        await retriever.aretrieve("q")
    assert len(conn.queries) == 1


@pytest.mark.asyncio
async def test_retriever_reports_no_current_run(fake_db):
    retriever = make_retriever(FakeConnection(None), FakeClock())

    with pytest.raises(NoCurrentRunError):
        await retriever.aretrieve("q")
    assert fake_db.created == []


def test_vector_db_does_not_create_missing_table(monkeypatch):
    monkeypatch.setattr(retriever_module.HanaDB, "_table_exists", lambda self, name: False)
    db = object.__new__(retriever_module.HanaVectorDB)
    db.table_name = RUN_A

    with pytest.raises(TableNotFoundError):
        db._initialize_table()


def test_hana_db_logger_is_silenced():
    # Its ERROR lines carry the full query vector; a dropped table is expected and retried.
    assert logging.getLogger("langchain_hana.vectorstores.hana_db").level == logging.CRITICAL


def _latency_count(is_success: bool) -> float:
    value = CustomMetrics().registry.get_sample_value(
        f"{HANADB_LATENCY_METRIC_KEY}_count", {"is_success": str(is_success)}
    )
    return value or 0


@pytest.mark.asyncio
async def test_retriever_records_success_latency(fake_db):
    retriever = make_retriever(FakeConnection(RUN_A), FakeClock())
    before = _latency_count(True)

    await retriever.aretrieve("q")

    assert _latency_count(True) > before


@pytest.mark.asyncio
async def test_retriever_records_failure_latency(fake_db):
    retriever = make_retriever(FakeConnection(None), FakeClock())
    before = _latency_count(False)

    with pytest.raises(NoCurrentRunError):
        await retriever.aretrieve("q")

    assert _latency_count(False) > before
