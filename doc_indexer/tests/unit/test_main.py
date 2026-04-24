from unittest.mock import Mock, patch

import pytest

pytestmark = pytest.mark.unit

EMBEDDING_MODEL_NAME = "text-embedding-3-large"
EMBEDDING_DEPLOYMENT_ID = "test-deployment-id-1234"


@pytest.fixture
def mock_embedding_model_config():
    config = Mock()
    config.name = EMBEDDING_MODEL_NAME
    config.deployment_id = EMBEDDING_DEPLOYMENT_ID
    return config


@pytest.fixture
def mock_embeddings():
    return Mock()


@pytest.fixture
def mock_hana_conn():
    return Mock()


def test_run_indexer_passes_model_name_not_deployment_id(mock_embedding_model_config, mock_embeddings, mock_hana_conn):
    """Ensure run_indexer passes the model name (not deployment_id) to create_embedding.

    Regression test for: ValueError: Model '<deployment_id>' not found in config file.
    """
    from main import run_indexer

    mock_factory = Mock(return_value=mock_embeddings)

    with (
        patch("main.get_embedding_model_config", return_value=mock_embedding_model_config) as mock_get_config,
        patch("main.create_embedding_factory", return_value=mock_factory),
        patch("main.AdaptiveSplitMarkdownIndexer") as mock_indexer_cls,
    ):
        mock_indexer_cls.return_value.index = Mock()
        run_indexer(hana_conn=mock_hana_conn)

    # The embedding factory must be called with the model name, not the deployment ID.
    mock_get_config.assert_called_once_with(EMBEDDING_MODEL_NAME)
    mock_factory.assert_called_once_with(EMBEDDING_MODEL_NAME)
    assert mock_factory.call_args[0][0] != EMBEDDING_DEPLOYMENT_ID, (
        "run_indexer passed deployment_id instead of model name to create_embedding"
    )


def test_run_indexer_uses_injected_embeddings_and_connection(mock_embeddings, mock_hana_conn):
    """run_indexer skips model/DB creation when dependencies are injected."""
    from main import run_indexer

    with (
        patch("main.get_embedding_model_config") as mock_get_config,
        patch("main.create_hana_connection") as mock_create_conn,
        patch("main.AdaptiveSplitMarkdownIndexer") as mock_indexer_cls,
    ):
        mock_indexer_cls.return_value.index = Mock()
        run_indexer(embeddings_model=mock_embeddings, hana_conn=mock_hana_conn)

    # Neither model nor connection creation should be called when injected.
    mock_get_config.assert_not_called()
    mock_create_conn.assert_not_called()
    mock_indexer_cls.assert_called_once()


def test_run_indexer_routes_to_local_when_index_to_file(mock_hana_conn):
    """When INDEX_TO_FILE=true, run_indexer must use the local ChromaDB path."""
    from main import run_indexer

    with (
        patch("main.INDEX_TO_FILE", True),
        patch("main._run_local_file_indexer") as mock_local,
    ):
        run_indexer(hana_conn=mock_hana_conn)

    mock_local.assert_called_once()


def test_run_indexer_never_touches_hana_when_index_to_file():
    """When INDEX_TO_FILE=true, no HANA connection must be created or used."""
    from main import run_indexer

    with (
        patch("main.INDEX_TO_FILE", True),
        patch("main._run_local_file_indexer"),
        patch("main.create_hana_connection") as mock_create_conn,
        patch("main.AdaptiveSplitMarkdownIndexer") as mock_adaptive,
    ):
        run_indexer()

    mock_create_conn.assert_not_called()
    mock_adaptive.assert_not_called()


def test_run_local_file_indexer_creates_indexer_and_packages():
    """_run_local_file_indexer must build a LocalFileIndexer and call package."""
    from main import _run_local_file_indexer

    with (
        patch("main.fastembed_embedding_creator"),
        patch("main.INDEX_OUTPUT_DIR", "/tmp/test_index"),
        patch("main.KYMA_VERSION", "test-version"),
        # LocalFileIndexer is lazily imported inside the function,
        # so we must patch it at its source module.
        patch("indexing.local_file_indexer.LocalFileIndexer") as mock_cls,
    ):
        mock_instance = Mock()
        mock_cls.return_value = mock_instance

        _run_local_file_indexer(docs_path="/docs", collection_name="kyma_docs")

    mock_cls.assert_called_once()
    mock_instance.index.assert_called_once()
    mock_cls.package.assert_called_once_with("/tmp/test_index", "kyma-docs-index-test-version.tar.gz")
