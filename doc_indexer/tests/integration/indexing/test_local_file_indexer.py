"""Integration tests for the local file indexing chain.

These tests use the real fastembed model (nomic-ai/nomic-embed-text-v1.5) and
a real ChromaDB PersistentClient to verify the entire Python pipeline:

    load docs -> chunk -> embed (fastembed) -> ChromaDB -> tar.gz

No external credentials or API keys are required — fastembed runs entirely
locally. The model is downloaded once (~274 MB) on first run and cached in
~/.cache/fastembed/.

Run with:
    cd doc_indexer
    poetry install --with local --with test
    poetry run pytest tests/integration/indexing/test_local_file_indexer.py -v
"""

import tarfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

FASTEMBED_MODEL = "nomic-ai/nomic-embed-text-v1.5"
E2E_DOCS_PATH = str(Path(__file__).parent.parent / "fixtures" / "e2e_docs" / "kyma-docs")


@pytest.fixture(scope="module")
def require_local_deps():
    """Skip the entire module if chromadb / fastembed are not installed."""
    try:
        import chromadb  # noqa: F401
        from fastembed import TextEmbedding  # noqa: F401
    except ImportError as exc:
        pytest.skip(f"Local deps not installed — run `poetry install --with local`: {exc}")


@pytest.fixture(scope="module")
def real_embedding(require_local_deps):
    """Load the fastembed model once for the whole module (slow, ~274 MB download)."""
    from utils.models import fastembed_embedding_creator

    return fastembed_embedding_creator(FASTEMBED_MODEL)


# ---------------------------------------------------------------------------
# Embedding model smoke tests
# ---------------------------------------------------------------------------


def test_fastembed_produces_768d_vectors(real_embedding):
    """nomic-embed-text-v1.5 must produce 768-dimensional vectors."""
    vectors = real_embedding.embed_documents(["Hello Kyma", "Serverless functions"])
    assert len(vectors) == 2
    assert len(vectors[0]) == 768, f"Expected 768-dim vectors, got {len(vectors[0])}"


def test_fastembed_embed_query_matches_doc_dimension(real_embedding):
    vec = real_embedding.embed_query("what is Kyma?")
    assert len(vec) == 768
    assert all(isinstance(x, float) for x in vec)


# ---------------------------------------------------------------------------
# Full indexing chain
# ---------------------------------------------------------------------------


def test_local_file_indexer_stores_chunks_in_chromadb(real_embedding, tmp_path):
    """Full chain: markdown -> chunks -> fastembed vectors -> ChromaDB."""
    import chromadb
    from indexing.local_file_indexer import LocalFileIndexer

    output_dir = str(tmp_path / "chroma")
    indexer = LocalFileIndexer(
        docs_path=E2E_DOCS_PATH,
        embedding=real_embedding,
        output_dir=output_dir,
        collection_name="kyma_docs",
    )
    indexer.index()

    client = chromadb.PersistentClient(path=output_dir)
    col = client.get_collection("kyma_docs")

    assert col.count() > 0, "Expected at least one chunk stored in ChromaDB"


def test_local_file_indexer_chunks_are_queryable(real_embedding, tmp_path):
    """Stored vectors must be retrievable via a similarity query."""
    import chromadb
    from indexing.local_file_indexer import LocalFileIndexer

    output_dir = str(tmp_path / "chroma")
    indexer = LocalFileIndexer(
        docs_path=E2E_DOCS_PATH,
        embedding=real_embedding,
        output_dir=output_dir,
        collection_name="kyma_docs",
    )
    indexer.index()

    client = chromadb.PersistentClient(path=output_dir)
    col = client.get_collection("kyma_docs")

    # Query using pre-computed embedding (chromadb without embedding_function
    # requires query_embeddings, not query_texts)
    query_vec = real_embedding.embed_query("Kyma architecture control plane")
    results = col.query(
        query_embeddings=[query_vec],
        n_results=2,
        include=["documents", "metadatas"],
    )

    assert len(results["documents"][0]) > 0
    # every returned chunk must have a title in its metadata
    for meta in results["metadatas"][0]:
        assert "title" in meta, f"Missing 'title' in metadata: {meta}"


def test_local_file_indexer_metadata_has_no_none_values(real_embedding, tmp_path):
    """ChromaDB rejects None metadata values — none must reach the collection."""
    import chromadb
    from indexing.local_file_indexer import LocalFileIndexer

    output_dir = str(tmp_path / "chroma")
    indexer = LocalFileIndexer(
        docs_path=E2E_DOCS_PATH,
        embedding=real_embedding,
        output_dir=output_dir,
        collection_name="kyma_docs",
    )
    indexer.index()

    client = chromadb.PersistentClient(path=output_dir)
    col = client.get_collection("kyma_docs")
    results = col.get(include=["metadatas"])

    for meta in results["metadatas"]:
        assert None not in meta.values(), f"None value found in metadata: {meta}"


def test_local_file_indexer_idempotent(real_embedding, tmp_path):
    """Running index() twice must not duplicate chunks."""
    import chromadb
    from indexing.local_file_indexer import LocalFileIndexer

    output_dir = str(tmp_path / "chroma")
    indexer = LocalFileIndexer(
        docs_path=E2E_DOCS_PATH,
        embedding=real_embedding,
        output_dir=output_dir,
        collection_name="kyma_docs",
    )
    indexer.index()
    count_first = chromadb.PersistentClient(path=output_dir).get_collection("kyma_docs").count()

    indexer.index()
    count_second = chromadb.PersistentClient(path=output_dir).get_collection("kyma_docs").count()

    assert count_first == count_second, f"Second run duplicated documents: {count_first} -> {count_second}"


# ---------------------------------------------------------------------------
# tar.gz packaging
# ---------------------------------------------------------------------------


def test_package_creates_valid_targz(real_embedding, tmp_path):
    """package() must produce a .tar.gz containing the ChromaDB sqlite3 file."""
    from indexing.local_file_indexer import LocalFileIndexer

    output_dir = str(tmp_path / "chroma")
    archive = str(tmp_path / "kyma-docs-index-test.tar.gz")

    indexer = LocalFileIndexer(
        docs_path=E2E_DOCS_PATH,
        embedding=real_embedding,
        output_dir=output_dir,
        collection_name="kyma_docs",
    )
    indexer.index()
    LocalFileIndexer.package(output_dir, archive)

    assert Path(archive).exists()
    with tarfile.open(archive, "r:gz") as tar:
        names = tar.getnames()

    assert any("sqlite3" in n for n in names), f"ChromaDB sqlite3 not found in archive. Members: {names}"


def test_packaged_archive_can_be_restored_and_queried(real_embedding, tmp_path):
    """Extract the archive and verify the restored ChromaDB is queryable."""
    import chromadb
    from indexing.local_file_indexer import LocalFileIndexer

    output_dir = str(tmp_path / "chroma")
    archive = str(tmp_path / "kyma-docs-index-test.tar.gz")
    restore_dir = str(tmp_path / "restored")

    indexer = LocalFileIndexer(
        docs_path=E2E_DOCS_PATH,
        embedding=real_embedding,
        output_dir=output_dir,
        collection_name="kyma_docs",
    )
    indexer.index()
    count_original = chromadb.PersistentClient(path=output_dir).get_collection("kyma_docs").count()

    LocalFileIndexer.package(output_dir, archive)

    # Extract into a fresh directory
    Path(restore_dir).mkdir()
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(restore_dir)

    # The archive contains a single top-level directory (the chroma dir basename)
    restored_chroma = next(Path(restore_dir).iterdir())
    client = chromadb.PersistentClient(path=str(restored_chroma))
    col = client.get_collection("kyma_docs")

    assert col.count() == count_original, f"Restored count {col.count()} != original {count_original}"
