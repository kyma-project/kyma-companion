import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from utils.hana import VerifyStats, verify_table

pytestmark = pytest.mark.unit

MODULES = ["istio", "api-gateway"]


@pytest.fixture
def sources_file(tmp_path: Path) -> str:
    path = tmp_path / "docs_sources.json"
    path.write_text(
        json.dumps(
            [
                {"name": name, "source_type": "Github", "url": f"https://github.com/kyma-project/{name}.git"}
                for name in MODULES
            ]
        )
    )
    return str(path)


def _stats(
    total_rows: int = 200,
    zero_row_modules: list[str] | None = None,
    duplicate_chunks: int = 0,
    oversized_chunks: int = 0,
    missing_metadata_rows: int = 0,
) -> VerifyStats:
    return VerifyStats(
        total_rows=total_rows,
        rows_per_module={"istio": total_rows},
        zero_row_modules=zero_row_modules or [],
        duplicate_chunks=duplicate_chunks,
        oversized_chunks=oversized_chunks,
        missing_metadata_rows=missing_metadata_rows,
    )


@pytest.mark.parametrize(
    "stats",
    [
        pytest.param(_stats(total_rows=0), id="empty table"),
        pytest.param(_stats(zero_row_modules=["api-gateway"]), id="module with zero rows"),
        pytest.param(_stats(missing_metadata_rows=5), id="missing metadata"),
    ],
)
def test_run_verify_exits_1_on_error(stats: VerifyStats, sources_file: str) -> None:
    from main import run_verify

    with patch("main.verify_table", return_value=stats), pytest.raises(SystemExit) as exc_info:
        run_verify(hana_conn=MagicMock(), table_name="test_table", sources_file=sources_file)

    assert exc_info.value.code == 1


def test_run_verify_passes_with_warnings_only(sources_file: str) -> None:
    """Duplicates and oversized chunks are warnings and must not fail the run."""
    from main import run_verify

    hana_conn = MagicMock()
    stats = _stats(duplicate_chunks=3, oversized_chunks=2)

    with (
        patch("main.create_hana_connection") as mock_create,
        patch("main.verify_table", return_value=stats) as mock_verify,
        patch("main.DATABASE_USER", "test_user"),
    ):
        run_verify(hana_conn=hana_conn, table_name="test_table", sources_file=sources_file)

    mock_create.assert_not_called()
    mock_verify.assert_called_once_with(hana_conn, "test_user", "test_table", MODULES)


def test_run_verify_raises_when_connection_fails(sources_file: str) -> None:
    from main import run_verify

    with (
        patch("main.create_hana_connection", return_value=None),
        pytest.raises(RuntimeError, match="Failed to connect to the database"),
    ):
        run_verify(sources_file=sources_file)


def test_run_verify_raises_when_sources_file_missing(tmp_path: Path) -> None:
    """Without the sources file the zero-row check cannot run, so verify must not pass."""
    from main import run_verify

    with pytest.raises(FileNotFoundError):
        run_verify(hana_conn=MagicMock(), sources_file=str(tmp_path / "missing.json"))


def test_verify_table_builds_stats_from_query_results() -> None:
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    # total rows, duplicates, oversized, missing metadata -- in query order
    cursor.fetchone.side_effect = [(120,), (3,), (2,), (5,)]
    cursor.fetchall.return_value = [("istio", 120)]

    stats = verify_table(connection, "test_user", "test_table", MODULES)

    assert stats == VerifyStats(
        total_rows=120,
        rows_per_module={"istio": 120},
        zero_row_modules=["api-gateway"],
        duplicate_chunks=3,
        oversized_chunks=2,
        missing_metadata_rows=5,
    )
    assert all('"test_user"."test_table"' in call.args[0] for call in cursor.execute.call_args_list)
