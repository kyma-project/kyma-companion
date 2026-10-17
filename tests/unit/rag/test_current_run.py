"""Tests for the lookup of the current run of a corpus (no live HANA)."""

import logging

import pytest

from rag.current_run import (
    CurrentRunTable,
    InvalidRunTableError,
    NoCurrentRunError,
    UnsupportedSchemaError,
    schema_major,
)
from unit.rag.fakes import RUN_A, RUN_B, FakeClock, FakeConnection, make_lookup, run_id

# Two lookups (or log lines, or warnings): the first one and the one after a change.
TWICE = 2


def test_resolve_queries_run_table():
    conn = FakeConnection(RUN_A)

    assert make_lookup(conn).resolve() == RUN_A
    sql, params = conn.queries[0]
    assert sql == (
        'SELECT run_id, table_name, is_current, schema_version FROM "docs_index_runs" '
        "WHERE corpus = ? AND (is_current = TRUE OR committed_at IS NOT NULL) "
        "ORDER BY committed_at DESC"
    )
    assert params == ("ops_docs",)


def test_resolve_is_cached_within_ttl():
    conn, clock = FakeConnection(RUN_A), FakeClock()
    lookup = make_lookup(conn, clock)

    lookup.resolve()
    conn.current = RUN_B
    clock.now = 59

    assert lookup.resolve() == RUN_A
    assert len(conn.queries) == 1


def test_resolve_again_after_ttl():
    conn, clock = FakeConnection(RUN_A), FakeClock()
    lookup = make_lookup(conn, clock)

    lookup.resolve()
    conn.current = RUN_B
    clock.now = 60

    assert lookup.resolve() == RUN_B
    assert len(conn.queries) == TWICE


def test_invalidate_forces_lookup():
    conn = FakeConnection(RUN_A)
    lookup = make_lookup(conn)

    lookup.resolve()
    conn.current = RUN_B
    assert lookup.invalidate(RUN_A) is True

    assert lookup.resolve() == RUN_B


def test_invalidate_keeps_a_newer_table():
    conn = FakeConnection(RUN_A)
    lookup = make_lookup(conn)
    lookup.resolve()
    conn.current = RUN_B
    lookup.invalidate(RUN_A)
    lookup.resolve()

    # A late retry that failed on the old table must not wipe the new one.
    assert lookup.invalidate(RUN_A) is False

    assert lookup.resolve() == RUN_B
    assert len(conn.queries) == TWICE


def test_current_run_table_logged_once_per_change(caplog):
    conn = FakeConnection(RUN_A)
    lookup = make_lookup(conn)

    with caplog.at_level(logging.INFO, logger="rag.current_run"):
        lookup.resolve()
        lookup.invalidate(RUN_A)
        lookup.resolve()
        conn.current = RUN_B
        lookup.invalidate(RUN_A)
        lookup.resolve()

    logged = [r.getMessage() for r in caplog.records if "Current run table" in r.getMessage()]
    assert logged == [
        f"Current run table of corpus ops_docs: {RUN_A} (schema_version 1.0)",
        f"Current run table of corpus ops_docs: {RUN_B} (schema_version 1.0)",
    ]


def test_no_current_run_is_an_error():
    with pytest.raises(NoCurrentRunError, match="corpus ops_docs has no current run in docs_index_runs"):
        make_lookup(FakeConnection(None)).resolve()


@pytest.mark.parametrize(
    "table",
    [
        "ops_docs",  # the legacy fixed table
        "ops_docs_",
        "kyma_docs_20261014093512_7be204",  # another corpus
        "opsXdocs_20261014093512_7be204",
        "ops_docs_20261014093512_7BE204",
        "OPS_DOCS_20261014093512_7be204",
        'ops_docs_20261014093512_7be204"; DROP TABLE x; --',
        "ops_docs_2026-10-14",
        "ops_docs_run 1",
    ],
)
def test_invalid_table_name_is_refused(table):
    with pytest.raises(InvalidRunTableError):
        make_lookup(FakeConnection(table)).resolve()


@pytest.mark.parametrize(
    "table",
    [
        RUN_A,  # <corpus>_<14 digits>_<6 hex>, as the indexer writes it today
        "ops_docs_20261014093512_7be204_2",
        "ops_docs_1",
        "ops_docs_run_abc",
    ],
)
def test_table_with_corpus_prefix_is_accepted(table):
    # Only the prefix <corpus>_ is part of the indexer contract.
    assert make_lookup(FakeConnection(table)).resolve() == table


def test_invalid_runs_table_name_is_refused():
    with pytest.raises(ValueError):
        CurrentRunTable(FakeConnection(RUN_A), "ops_docs", 'runs"; --', 60)  # type: ignore[arg-type]


RUN_OLD = "ops_docs_20261013080000_123abc"


def warnings(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]


@pytest.mark.parametrize("version", ["1.0", "1.7", None])
def test_supported_current_run_is_used(version, caplog):
    conn = FakeConnection(RUN_A, version, older=[(RUN_OLD, "1.0")])

    with caplog.at_level(logging.INFO, logger="rag.current_run"):
        assert make_lookup(conn).resolve() == RUN_A
    assert warnings(caplog) == []


def test_null_schema_version_means_1_0(caplog):
    with caplog.at_level(logging.INFO, logger="rag.current_run"):
        assert make_lookup(FakeConnection(RUN_A, None)).resolve() == RUN_A
    assert f"{RUN_A} (schema_version 1.0)" in caplog.text


def test_missing_schema_version_column_means_1_0():
    conn = FakeConnection(RUN_A, has_column=False)
    lookup = make_lookup(conn)

    assert lookup.resolve() == RUN_A
    lookup.invalidate(RUN_A)
    assert lookup.resolve() == RUN_A
    assert "NULL" in conn.queries[0][0]
    # Still missing, so asked again: an indexer may add the column at any time.
    assert conn.column_checks == TWICE


def test_schema_version_column_checked_once():
    conn = FakeConnection(RUN_A)
    lookup = make_lookup(conn)

    lookup.resolve()
    lookup.invalidate(RUN_A)
    lookup.resolve()

    assert conn.column_checks == 1


def test_unsupported_current_run_falls_back_and_warns_once(caplog):
    conn = FakeConnection(RUN_B, "2.0", older=[(RUN_A, "2.1"), (RUN_OLD, "1.3")])
    lookup = make_lookup(conn)

    with caplog.at_level(logging.INFO, logger="rag.current_run"):
        assert lookup.resolve() == RUN_OLD
        lookup.invalidate(RUN_OLD)
        assert lookup.resolve() == RUN_OLD

    assert warnings(caplog) == [
        f"current run {run_id(RUN_B)} of corpus ops_docs has schema_version '2.0', this server "
        f"supports major 1; serving older run {run_id(RUN_OLD)} (schema 1.3). "
        "Update kyma-companion."
    ]


def test_fallback_is_logged_as_serving_not_current(caplog):
    conn = FakeConnection(RUN_B, "2.0", older=[(RUN_OLD, "1.3")])

    with caplog.at_level(logging.INFO, logger="rag.current_run"):
        make_lookup(conn).resolve()

    infos = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert infos == [
        f"Serving run table of corpus ops_docs: {RUN_OLD} (schema_version 1.3, fallback from "
        f"current run {run_id(RUN_B)} with schema_version '2.0')"
    ]
    assert "Current run table" not in caplog.text


def test_fallback_ignores_null_is_current_and_order(caplog):
    # Ordered by committed_at only: the current run may be anywhere, and is_current may be NULL.
    rows = [
        ("r_newest", RUN_A, None, "1.0"),
        ("r_current", RUN_B, True, "2.0"),
        ("r_old", RUN_OLD, False, "1.0"),
    ]
    conn = FakeConnection(RUN_B)
    conn.answer = lambda sql, params: [(1,)] if "TABLE_COLUMNS" in sql else rows  # type: ignore[method-assign]

    assert make_lookup(conn).resolve() == RUN_A


def test_current_run_is_picked_by_its_flag_not_its_position():
    rows = [
        ("r_newer", RUN_A, None, "1.0"),
        ("r_current", RUN_B, True, "1.0"),
    ]
    conn = FakeConnection(RUN_B)
    conn.answer = lambda sql, params: [(1,)] if "TABLE_COLUMNS" in sql else rows  # type: ignore[method-assign]

    assert make_lookup(conn).resolve() == RUN_B


def test_recovery_after_unsupported_error_is_logged_again(caplog):
    conn = FakeConnection(RUN_B, "2.0", older=[(RUN_A, "1.0")])
    lookup = make_lookup(conn)

    with caplog.at_level(logging.INFO, logger="rag.current_run"):
        assert lookup.resolve() == RUN_A
        conn.older = [(RUN_A, "3.0")]
        lookup.invalidate(RUN_A)
        with pytest.raises(UnsupportedSchemaError):
            lookup.resolve()
        conn.older = [(RUN_A, "1.0")]
        assert lookup.resolve() == RUN_A

    assert len(warnings(caplog)) == TWICE
    assert [r.getMessage() for r in caplog.records if r.levelno == logging.INFO].count(
        f"Serving run table of corpus ops_docs: {RUN_A} (schema_version 1.0, fallback from "
        f"current run {run_id(RUN_B)} with schema_version '2.0')"
    ) == TWICE


@pytest.mark.parametrize("version", ["garbage", "2", "1.x", ""])
def test_unparseable_schema_version_falls_back(version, caplog):
    conn = FakeConnection(RUN_B, version, older=[(RUN_A, "1.0")])

    with caplog.at_level(logging.WARNING, logger="rag.current_run"):
        assert make_lookup(conn).resolve() == RUN_A
    assert f"schema_version {version!r} (unparseable)" in warnings(caplog)[0]


def test_unsupported_without_supported_older_run_is_an_error():
    conn = FakeConnection(RUN_B, "2.0", older=[(RUN_A, "2.0")])

    with pytest.raises(
        UnsupportedSchemaError,
        match=(
            f"corpus ops_docs: current run {run_id(RUN_B)} has unsupported schema_version "
            "'2.0' and no kept run with a supported major"
        ),
    ):
        make_lookup(conn).resolve()


def test_unsupported_error_names_the_versions_found():
    conn = FakeConnection(RUN_B, "2.0", older=[(RUN_A, "2.0"), (RUN_OLD, "3.1")])

    with pytest.raises(UnsupportedSchemaError, match=r"\(schema_versions found: '2.0', '3.1'\)$"):
        make_lookup(conn).resolve()


def test_no_current_run_does_not_fall_back():
    with pytest.raises(NoCurrentRunError):
        make_lookup(FakeConnection(None, older=[(RUN_A, "1.0")])).resolve()


def test_fallback_table_name_is_checked():
    conn = FakeConnection(RUN_B, "2.0", older=[("ops_docs", "1.0")])

    with pytest.raises(InvalidRunTableError, match="'ops_docs'"):
        make_lookup(conn).resolve()


@pytest.mark.parametrize(
    ("version", "major"),
    [(None, 1), ("1.0", 1), (" 1.12 ", 1), ("2.0", 2), ("1", None), ("v1.0", None)],
)
def test_schema_major(version, major):
    assert schema_major(version) == major
