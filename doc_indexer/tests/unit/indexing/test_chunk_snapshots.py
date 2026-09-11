"""Snapshot tests for the AdaptiveSplitMarkdownIndexer chunking output.

Run with UPDATE_SNAPSHOTS=1 to regenerate the committed snapshot file:

    UPDATE_SNAPSHOTS=1 poetry run pytest tests/unit/indexing/test_chunk_snapshots.py -v

Review the diff in tests/unit/fixtures/snapshots/chunks.json before committing.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from indexing.adaptive_indexer import AdaptiveSplitMarkdownIndexer
from utils.documents import load_documents

pytestmark = pytest.mark.unit

_FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "snapshot_docs"
_SNAPSHOT_FILE = Path(__file__).parent.parent / "fixtures" / "snapshots" / "chunks.json"


@pytest.fixture(scope="module")
def snapshot_indexer() -> AdaptiveSplitMarkdownIndexer:
    """Return an indexer backed by mocked HanaDB for snapshot testing."""
    mock_embedding = MagicMock()
    mock_connection = MagicMock()
    with patch("indexing.adaptive_indexer.HanaDB"):
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path=str(_FIXTURES_DIR),
            embedding=mock_embedding,
            connection=mock_connection,
            table_name="snapshot_test",
        )
    return indexer


def test_chunk_snapshot(snapshot_indexer: AdaptiveSplitMarkdownIndexer) -> None:
    """Chunk output must match the committed snapshot.

    When UPDATE_SNAPSHOTS=1 is set the snapshot file is regenerated instead of
    compared, so that a single run both updates and passes.
    """
    docs = load_documents(str(_FIXTURES_DIR))
    chunks = snapshot_indexer.build_chunks(docs)

    def _rel_source(raw: str) -> str:
        """Return path relative to the fixture root, using forward slashes."""
        try:
            return Path(raw).relative_to(_FIXTURES_DIR).as_posix()
        except ValueError:
            return raw

    serialized = sorted(
        [
            {
                "source": _rel_source(chunk.metadata.get("source", "")),
                "title": chunk.metadata.get("title", ""),
                "page_content": chunk.page_content,
            }
            for chunk in chunks
        ],
        key=lambda c: (c["source"], c["title"]),
    )

    if os.environ.get("UPDATE_SNAPSHOTS"):
        _SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
        _SNAPSHOT_FILE.write_text(
            json.dumps(serialized, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        pytest.skip("Snapshot updated -- re-run without UPDATE_SNAPSHOTS to verify.")
        return

    assert _SNAPSHOT_FILE.exists(), (
        f"Snapshot file not found: {_SNAPSHOT_FILE}\nRun with UPDATE_SNAPSHOTS=1 to create it."
    )

    committed = json.loads(_SNAPSHOT_FILE.read_text(encoding="utf-8"))
    assert serialized == committed, (
        "Chunk output changed. If the change is intentional, regenerate the snapshot:\n"
        "  UPDATE_SNAPSHOTS=1 poetry run pytest tests/unit/indexing/test_chunk_snapshots.py -v\n"
        "Then review and commit tests/unit/fixtures/snapshots/chunks.json."
    )
