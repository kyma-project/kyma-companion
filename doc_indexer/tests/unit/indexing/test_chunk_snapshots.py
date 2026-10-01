"""Snapshot test for the AdaptiveSplitMarkdownIndexer chunking output.

Run with UPDATE_SNAPSHOTS=1 to regenerate the committed snapshot file:

    UPDATE_SNAPSHOTS=1 poetry run pytest tests/unit/indexing/test_chunk_snapshots.py -v

Review the diff in tests/unit/fixtures/snapshots/chunks.json before committing.
"""

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

# repo, commit and url are left out: the fixtures have no fetch manifest, so they
# are either None or the machine-dependent local path.
_SNAPSHOT_KEYS = ("module", "path", "chunk_index", "total_chunks", "title", "heading")


def test_chunk_snapshot() -> None:
    """Chunk output must match the committed snapshot."""
    with patch("indexing.adaptive_indexer.HanaDB"):
        indexer = AdaptiveSplitMarkdownIndexer(
            docs_path=str(_FIXTURES_DIR),
            embedding=MagicMock(),
            connection=MagicMock(),
            table_name="snapshot_test",
        )
    chunks = indexer.build_chunks(load_documents(str(_FIXTURES_DIR)))

    serialized = sorted(
        (
            {**{key: chunk.metadata[key] for key in _SNAPSHOT_KEYS}, "page_content": chunk.page_content}
            for chunk in chunks
        ),
        key=lambda c: (c["module"], c["path"], c["chunk_index"]),
    )

    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        _SNAPSHOT_FILE.write_text(json.dumps(serialized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        pytest.skip("Snapshot updated -- re-run without UPDATE_SNAPSHOTS to verify.")

    committed = json.loads(_SNAPSHOT_FILE.read_text(encoding="utf-8"))
    assert serialized == committed, (
        "Chunk output changed. If the change is intentional, regenerate the snapshot:\n"
        "  UPDATE_SNAPSHOTS=1 poetry run pytest tests/unit/indexing/test_chunk_snapshots.py -v\n"
        "Then review and commit tests/unit/fixtures/snapshots/chunks.json."
    )
