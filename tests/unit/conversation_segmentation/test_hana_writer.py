import datetime as dt
from unittest.mock import MagicMock

import pytest

from conversation_segmentation import hana_writer

pytestmark = pytest.mark.unit


def _conn_with_cursor():
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    return conn, cur


def test_read_watermarks_maps_key_to_count():
    conn, cur = _conn_with_cursor()
    cur.fetchall.return_value = [("hash1", 3, "fp1"), ("hash2", 7, "fp2")]
    assert hana_writer.read_watermarks(conn, "AIFORCE2") == {"hash1": (3, "fp1"), "hash2": (7, "fp2")}


def test_write_run_inserts_upserts_prunes_then_commits_once():
    conn, cur = _conn_with_cursor()
    row = {"RUN_ID": 1, "TOTAL_TURNS": 2, "FAILED_TURNS": 0, "C_OTHER_SUFFICIENT": 2}
    hana_writer.write_run(conn, "AIFORCE2", row, {"h1": (2, "fpX")}, dt.datetime(2026, 9, 1))
    executed = " ".join(c.args[0].upper() for c in cur.execute.call_args_list)
    assert "INSERT INTO" in executed and "UPSERT" in executed and "DELETE FROM" in executed
    conn.commit.assert_called_once()  # atomic: exactly one commit for the whole run


def test_write_run_disables_autocommit_then_restores():
    conn, cur = _conn_with_cursor()
    row = {"RUN_ID": 1, "TOTAL_TURNS": 2, "FAILED_TURNS": 0, "C_OTHER_SUFFICIENT": 2}
    hana_writer.write_run(conn, "AIFORCE2", row, {"h1": (2, "fpX")}, dt.datetime(2026, 9, 1))
    # hdbcli defaults to autocommit=True; the run must turn it off, then restore it
    conn.setautocommit.assert_any_call(False)
    assert conn.setautocommit.call_args_list[-1].args == (True,)
    conn.rollback.assert_not_called()


def test_write_run_rolls_back_and_restores_autocommit_on_error():
    conn, cur = _conn_with_cursor()
    cur.execute.side_effect = RuntimeError("hana down mid-write")
    row = {"RUN_ID": 1, "TOTAL_TURNS": 2, "FAILED_TURNS": 0, "C_OTHER_SUFFICIENT": 2}
    with pytest.raises(RuntimeError):
        hana_writer.write_run(conn, "AIFORCE2", row, {"h1": (2, "fpX")}, dt.datetime(2026, 9, 1))
    conn.rollback.assert_called_once()  # partial write is undone as one transaction
    conn.commit.assert_not_called()
    assert conn.setautocommit.call_args_list[-1].args == (True,)  # restored even on failure
