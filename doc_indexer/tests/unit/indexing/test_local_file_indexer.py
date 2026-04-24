import sys
import tarfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from indexing.local_file_indexer import LocalFileIndexer, _clean_metadata

pytestmark = pytest.mark.unit

FIXTURES_PATH = str(Path(__file__).parent.parent / "fixtures" / "test_docs")


@pytest.fixture
def mock_embedding():
    m = MagicMock()
    m.embed_documents.side_effect = lambda texts, batch_size=32: [[0.1, 0.2, 0.3]] * len(texts)
    return m


@pytest.fixture
def mock_chroma_collection():
    col = MagicMock()
    col.count.return_value = 0
    return col


@pytest.fixture
def mock_chromadb(mock_chroma_collection, monkeypatch):
    """Inject a fake chromadb module into sys.modules.

    When index() runs `import chromadb`, Python resolves it from sys.modules,
    so it gets this mock instead of the real (uninstalled) library.
    """
    module = MagicMock()
    client = MagicMock()
    client.create_collection.return_value = mock_chroma_collection
    module.PersistentClient.return_value = client
    monkeypatch.setitem(sys.modules, "chromadb", module)
    return module


@pytest.fixture
def mock_chroma_client(mock_chromadb):
    return mock_chromadb.PersistentClient.return_value


@pytest.fixture
def indexer(mock_embedding, tmp_path):
    return LocalFileIndexer(
        docs_path=FIXTURES_PATH,
        embedding=mock_embedding,
        output_dir=str(tmp_path / "chroma"),
        collection_name="test_collection",
        # lower threshold so the small fixture docs produce chunks
        min_chunk_token_count=1,
    )


class TestCleanMetadata:
    def test_none_values_replaced_with_empty_string(self):
        result = _clean_metadata({"title": "Hello", "module": None, "version": None})
        assert result == {"title": "Hello", "module": "", "version": ""}

    def test_non_none_values_unchanged(self):
        result = _clean_metadata({"title": "T", "source": "s", "version": "1.0"})
        assert result == {"title": "T", "source": "s", "version": "1.0"}

    def test_empty_dict(self):
        assert _clean_metadata({}) == {}

    def test_mixed_types_preserved(self):
        result = _clean_metadata({"count": 5, "flag": True, "score": 0.9, "x": None})
        assert result == {"count": 5, "flag": True, "score": 0.9, "x": ""}


class TestLocalFileIndexerIndex:
    def test_index_deletes_existing_collection_before_creating(self, indexer, mock_chroma_client, mock_chromadb):
        indexer.index()

        mock_chroma_client.delete_collection.assert_called_once_with("test_collection")
        mock_chroma_client.create_collection.assert_called_once()

    def test_index_creates_collection_with_cosine_space(self, indexer, mock_chroma_client, mock_chromadb):
        indexer.index()

        _, kwargs = mock_chroma_client.create_collection.call_args
        assert kwargs["metadata"]["hnsw:space"] == "cosine"

    def test_index_calls_embed_documents_with_chunk_texts(self, indexer, mock_embedding, mock_chromadb):
        indexer.index()

        assert mock_embedding.embed_documents.called
        for call_args in mock_embedding.embed_documents.call_args_list:
            texts = call_args[0][0]
            assert isinstance(texts, list)
            assert all(isinstance(t, str) for t in texts)

    def test_index_adds_documents_to_collection(self, indexer, mock_chroma_collection, mock_chromadb):
        indexer.index()

        assert mock_chroma_collection.add.called

    def test_index_passes_ids_embeddings_documents_metadatas(self, indexer, mock_chroma_collection, mock_chromadb):
        indexer.index()

        for c in mock_chroma_collection.add.call_args_list:
            kwargs = c.kwargs
            assert "ids" in kwargs
            assert "embeddings" in kwargs
            assert "documents" in kwargs
            assert "metadatas" in kwargs
            n = len(kwargs["ids"])
            assert len(kwargs["embeddings"]) == n
            assert len(kwargs["documents"]) == n
            assert len(kwargs["metadatas"]) == n

    def test_index_metadata_has_no_none_values(self, indexer, mock_chroma_collection, mock_chromadb):
        indexer.index()

        for c in mock_chroma_collection.add.call_args_list:
            for meta in c.kwargs["metadatas"]:
                assert None not in meta.values(), f"Metadata contains None: {meta}"

    def test_index_continues_when_delete_collection_raises(
        self,
        indexer,
        mock_chroma_client,
        mock_chroma_collection,
        mock_chromadb,
    ):
        mock_chroma_client.delete_collection.side_effect = ValueError("not found")

        indexer.index()  # must not raise

        mock_chroma_client.create_collection.assert_called_once()


class TestLocalFileIndexerPackage:
    def test_package_creates_file(self, tmp_path):
        chroma_dir = tmp_path / "chroma"
        chroma_dir.mkdir()
        (chroma_dir / "dummy.sqlite3").write_text("x")

        archive = str(tmp_path / "out.tar.gz")
        LocalFileIndexer.package(str(chroma_dir), archive)

        assert Path(archive).exists()

    def test_package_produces_valid_targz(self, tmp_path):
        chroma_dir = tmp_path / "chroma"
        chroma_dir.mkdir()
        (chroma_dir / "chroma.sqlite3").write_text("data")

        archive = str(tmp_path / "test.tar.gz")
        LocalFileIndexer.package(str(chroma_dir), archive)

        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getnames()
        assert len(members) > 0

    def test_package_arcname_matches_output_dir_basename(self, tmp_path):
        chroma_dir = tmp_path / "chroma"
        chroma_dir.mkdir()
        (chroma_dir / "f.txt").write_text("x")

        archive = str(tmp_path / "test.tar.gz")
        LocalFileIndexer.package(str(chroma_dir), archive)

        with tarfile.open(archive, "r:gz") as tar:
            for member in tar.getmembers():
                assert member.name.startswith("chroma"), f"Unexpected archive path: {member.name}"
