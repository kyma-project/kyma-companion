"""Unit tests for the run_verify function and _print_verify_report helper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def _make_stats(
    total_rows: int = 100,
    rows_per_module: dict[str, int] | None = None,
    zero_row_modules: list[str] | None = None,
    duplicate_chunks: int = 0,
    oversized_chunks: int = 0,
    missing_metadata_rows: int = 0,
) -> object:
    """Build a VerifyStats object for use in tests."""
    from utils.hana import VerifyStats

    return VerifyStats(
        total_rows=total_rows,
        rows_per_module=rows_per_module or {},
        zero_row_modules=zero_row_modules or [],
        duplicate_chunks=duplicate_chunks,
        oversized_chunks=oversized_chunks,
        missing_metadata_rows=missing_metadata_rows,
    )


class TestRunVerify:
    """Tests for run_verify exit-code logic."""

    def test_exits_1_when_total_rows_zero(self) -> None:
        """run_verify exits with code 1 when the table is empty."""
        from main import run_verify

        stats = _make_stats(total_rows=0)
        mock_conn = MagicMock()

        with (
            patch("main.verify_table", return_value=stats),
            patch("main.DATABASE_USER", "test_user"),
            patch("main.open", MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))),
            patch("json.load", return_value=[]),
            pytest.raises(SystemExit) as exc_info,
        ):
            run_verify(hana_conn=mock_conn, table_name="test_table", sources_file="fake.json")

        assert exc_info.value.code == 1

    def test_exits_1_when_module_has_zero_rows(self) -> None:
        """run_verify exits with code 1 when a configured module has zero rows."""
        from main import run_verify

        stats = _make_stats(
            total_rows=50,
            rows_per_module={"istio": 50},
            zero_row_modules=["api-gateway"],
        )
        mock_conn = MagicMock()

        with (
            patch("main.verify_table", return_value=stats),
            patch("main.DATABASE_USER", "test_user"),
            patch("main.open", MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))),
            patch("json.load", return_value=[{"name": "api-gateway"}, {"name": "istio"}]),
            pytest.raises(SystemExit) as exc_info,
        ):
            run_verify(hana_conn=mock_conn, table_name="test_table", sources_file="fake.json")

        assert exc_info.value.code == 1

    def test_exits_1_when_missing_metadata(self) -> None:
        """run_verify exits with code 1 when rows are missing title or url."""
        from main import run_verify

        stats = _make_stats(
            total_rows=100,
            rows_per_module={"istio": 100},
            missing_metadata_rows=5,
        )
        mock_conn = MagicMock()

        with (
            patch("main.verify_table", return_value=stats),
            patch("main.DATABASE_USER", "test_user"),
            patch("main.open", MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))),
            patch("json.load", return_value=[{"name": "istio"}]),
            pytest.raises(SystemExit) as exc_info,
        ):
            run_verify(hana_conn=mock_conn, table_name="test_table", sources_file="fake.json")

        assert exc_info.value.code == 1

    def test_no_exit_when_healthy(self) -> None:
        """run_verify does not exit when all checks pass."""
        from main import run_verify

        stats = _make_stats(
            total_rows=200,
            rows_per_module={"istio": 100, "api-gateway": 100},
            zero_row_modules=[],
            duplicate_chunks=3,  # warning only
            oversized_chunks=2,  # warning only
            missing_metadata_rows=0,
        )
        mock_conn = MagicMock()

        with (
            patch("main.verify_table", return_value=stats),
            patch("main.DATABASE_USER", "test_user"),
            patch("main.open", MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))),
            patch("json.load", return_value=[{"name": "istio"}, {"name": "api-gateway"}]),
        ):
            # Should not raise SystemExit
            run_verify(hana_conn=mock_conn, table_name="test_table", sources_file="fake.json")

    def test_raises_runtime_error_when_connection_fails(self) -> None:
        """run_verify raises RuntimeError when no HANA connection can be created."""
        from main import run_verify

        with (
            patch("main.create_hana_connection", return_value=None),
            pytest.raises(RuntimeError, match="Failed to connect to the database"),
        ):
            run_verify()

    def test_uses_injected_connection(self) -> None:
        """run_verify skips connection creation when a connection is injected."""
        from main import run_verify

        stats = _make_stats(total_rows=10, rows_per_module={"istio": 10})
        mock_conn = MagicMock()

        with (
            patch("main.create_hana_connection") as mock_create,
            patch("main.verify_table", return_value=stats),
            patch("main.DATABASE_USER", "test_user"),
            patch("main.open", MagicMock(return_value=MagicMock(__enter__=MagicMock(), __exit__=MagicMock()))),
            patch("json.load", return_value=[{"name": "istio"}]),
        ):
            run_verify(hana_conn=mock_conn, table_name="test_table", sources_file="fake.json")

        mock_create.assert_not_called()
