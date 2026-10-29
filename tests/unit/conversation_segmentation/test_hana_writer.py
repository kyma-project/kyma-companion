import datetime as dt
from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from conversation_segmentation import hana_writer
from conversation_segmentation.aggregator import AssignmentState

pytestmark = pytest.mark.unit

_BULK_SIZE = 2


def _conn_with_cursor():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    return conn, cur


def _run_row():
    return {"RUN_ID": 1, "TURNS_ANALYZED": 2, "FAILED_TURNS": 0, "TAXONOMY_VERSION": "v1"}


def _assignment():
    return AssignmentState(
        conversation_hash="h1",
        topic_key="istio/troubleshooting/mtls",
        area="istio",
        intent="troubleshooting",
        capability="mtls",
        label="mTLS",
        summary="mtls broke",
        confidence=0.9,
        turn_count=2,
    )


def _aggregate_row():
    return {
        "TOPIC_KEY": "istio/troubleshooting/mtls",
        "AREA": "istio",
        "INTENT": "troubleshooting",
        "CAPABILITY": "mtls",
        "TOPIC_LABEL": "mTLS",
        "DISTINCT_CONVERSATION_COUNT": 1,
        "TURN_COUNT": 2,
        "EXAMPLE_SUMMARIES": ["mtls broke"],
        "TAXONOMY_VERSION": "v1",
    }


def test_read_watermarks_maps_key_to_count():
    conn, cur = _conn_with_cursor()
    cur.fetchall.return_value = [("hash1", 3, "fp1"), ("hash2", 7, "fp2")]
    assert hana_writer.read_watermarks(conn, "AIFORCE2") == {"hash1": (3, "fp1"), "hash2": (7, "fp2")}


def test_ensure_tables_creates_absent_tables_and_commits_once():
    conn, cur = _conn_with_cursor()
    cur.fetchone.return_value = (0,)  # every table reported absent
    hana_writer.ensure_tables(conn, "AIFORCE2")
    creates = [c for c in cur.execute.call_args_list if c.args[0].upper().startswith("CREATE TABLE")]
    assert len(creates) == 4  # noqa: PLR2004  # the four topic-analysis tables
    conn.commit.assert_called_once()


def test_ensure_tables_validates_existing_table_columns_without_recreating():
    conn, cur = _conn_with_cursor()
    cur.fetchone.return_value = (1,)  # every table exists
    all_columns = (
        hana_writer._RUN_COLUMNS
        | hana_writer._ASSIGNMENT_COLUMNS
        | hana_writer._AGGREGATE_COLUMNS
        | hana_writer._WATERMARK_COLUMNS
    )
    cur.fetchall.return_value = [(column,) for column in all_columns]

    hana_writer.ensure_tables(conn, "AIFORCE2")

    creates = [call for call in cur.execute.call_args_list if call.args[0].upper().startswith("CREATE TABLE")]
    assert creates == []
    conn.commit.assert_called_once()


def test_validate_table_columns_rejects_incompatible_existing_table():
    conn, cur = _conn_with_cursor()
    cur.fetchall.return_value = [("RUN_ID",)]

    with pytest.raises(RuntimeError, match="CREATED_AT.*TAXONOMY_VERSION"):
        hana_writer._validate_table_columns(conn, "AIFORCE2", "RUNS", hana_writer._RUN_COLUMNS)


def test_ensure_tables_rejects_unsafe_identifier():
    conn, _ = _conn_with_cursor()
    with pytest.raises(ValueError, match="Unsafe SQL identifier"):
        hana_writer.ensure_tables(conn, "AIFORCE2; DROP TABLE X")


def test_read_last_window_end_none_on_first_run():
    conn, cur = _conn_with_cursor()
    cur.fetchone.return_value = (None,)
    assert hana_writer.read_last_window_end(conn, "AIFORCE2") is None


def test_read_last_window_end_returns_max():
    conn, cur = _conn_with_cursor()
    cur.fetchone.return_value = (dt.datetime(2026, 9, 1),)
    assert hana_writer.read_last_window_end(conn, "AIFORCE2") == dt.datetime(2026, 9, 1)


def test_validate_taxonomy_version_accepts_current_or_empty_history():
    conn, cur = _conn_with_cursor()
    cur.fetchall.return_value = [("v1",)]
    hana_writer.validate_taxonomy_version(conn, "AIFORCE2")

    cur.fetchall.return_value = []
    hana_writer.validate_taxonomy_version(conn, "AIFORCE2")


def test_validate_taxonomy_version_rejects_stale_history():
    conn, cur = _conn_with_cursor()
    cur.fetchall.return_value = [("v0",), ("v1",)]

    with pytest.raises(hana_writer.TaxonomyVersionMismatchError, match="v0.*v1"):
        hana_writer.validate_taxonomy_version(conn, "AIFORCE2")


def test_read_assignments_builds_states():
    conn, cur = _conn_with_cursor()
    cur.fetchall.return_value = [
        ("h1", "istio/troubleshooting/mtls", "istio", "troubleshooting", "mtls", "mTLS", "s", 0.9, 2, "v1"),
    ]
    states = hana_writer.read_assignments(conn, "AIFORCE2")
    assert len(states) == 1
    assert states[0].topic_key == "istio/troubleshooting/mtls"
    assert states[0].turn_count == 2  # noqa: PLR2004
    assert states[0].taxonomy_version == "v1"


def test_write_batch_upserts_assignments_and_watermarks_then_commits_once():
    conn, cur = _conn_with_cursor()
    second_assignment = replace(
        _assignment(),
        conversation_hash="h2",
        topic_key="kubernetes/troubleshooting/pods",
    )
    hana_writer.write_batch(
        conn,
        "AIFORCE2",
        assignments=[_assignment(), second_assignment],
        watermarks={"h1": (2, "fpX"), "h2": (1, "fpY")},
        run_id=1,
        now=dt.datetime(2026, 10, 1),
    )
    assert cur.executemany.call_count == _BULK_SIZE  # one bulk call each for assignments and watermarks
    assert all("UPSERT" in call.args[0].upper() for call in cur.executemany.call_args_list)
    assert len(cur.executemany.call_args_list[0].args[1]) == _BULK_SIZE  # assignments share one round trip
    assert len(cur.executemany.call_args_list[1].args[1]) == _BULK_SIZE  # watermarks share one round trip
    conn.commit.assert_called_once()  # atomic per batch
    assert conn.setautocommit.call_args_list[-1].args == (True,)  # autocommit restored


def test_write_batch_is_noop_when_nothing_changed():
    conn, _ = _conn_with_cursor()
    hana_writer.write_batch(conn, "AIFORCE2", assignments=[], watermarks={}, run_id=1, now=dt.datetime(2026, 10, 1))
    conn.setautocommit.assert_not_called()  # no transaction opened
    conn.commit.assert_not_called()


def test_write_batch_rolls_back_and_restores_autocommit_on_error():
    conn, cur = _conn_with_cursor()
    cur.executemany.side_effect = RuntimeError("hana down mid-batch")
    with pytest.raises(RuntimeError):
        hana_writer.write_batch(
            conn,
            "AIFORCE2",
            assignments=[_assignment()],
            watermarks={"h1": (2, "fpX")},
            run_id=1,
            now=dt.datetime(2026, 10, 1),
        )
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    assert conn.setautocommit.call_args_list[-1].args == (True,)


def test_write_run_inserts_run_and_replaces_aggregate_then_commits_once():
    conn, cur = _conn_with_cursor()
    second_aggregate = {
        **_aggregate_row(),
        "TOPIC_KEY": "kubernetes/troubleshooting/pods",
        "AREA": "kubernetes",
        "CAPABILITY": "pods",
    }
    hana_writer.write_run(
        conn,
        "AIFORCE2",
        run_row=_run_row(),
        aggregate_rows=[_aggregate_row(), second_aggregate],
        now=dt.datetime(2026, 10, 1),
    )
    executed = " ".join(c.args[0].upper() for c in cur.execute.call_args_list)
    assert "INSERT INTO" in executed and "DELETE FROM" in executed
    cur.executemany.assert_called_once()
    assert "INSERT INTO" in cur.executemany.call_args.args[0].upper()
    assert len(cur.executemany.call_args.args[1]) == _BULK_SIZE  # aggregate rows share one round trip
    conn.commit.assert_called_once()  # atomic: one commit to finalize the run


def test_write_run_rolls_back_and_restores_autocommit_on_error():
    conn, cur = _conn_with_cursor()
    cur.execute.side_effect = RuntimeError("hana down mid-write")
    with pytest.raises(RuntimeError):
        hana_writer.write_run(
            conn,
            "AIFORCE2",
            run_row=_run_row(),
            aggregate_rows=[_aggregate_row()],
            now=dt.datetime(2026, 10, 1),
        )
    conn.rollback.assert_called_once()
    conn.commit.assert_not_called()
    assert conn.setautocommit.call_args_list[-1].args == (True,)  # restored even on failure
