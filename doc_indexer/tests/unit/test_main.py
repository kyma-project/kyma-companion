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


def test_run_drop_calls_drop_table_with_injected_connection(mock_hana_conn):
    """run_drop calls drop_table with the injected connection and configured table name."""
    from main import run_drop

    with (
        patch("main.drop_table") as mock_drop,
        patch("main.DATABASE_USER", "test_user"),
    ):
        run_drop(hana_conn=mock_hana_conn, table_name="test_table")

    mock_drop.assert_called_once_with(mock_hana_conn, "test_user", "test_table")


def test_run_drop_accepts_explicit_table_name(mock_hana_conn):
    """run_drop uses the explicitly provided table_name instead of the config default."""
    from main import run_drop

    with (
        patch("main.drop_table") as mock_drop,
        patch("main.DATABASE_USER", "test_user"),
    ):
        run_drop(hana_conn=mock_hana_conn, table_name="custom_table")

    mock_drop.assert_called_once_with(mock_hana_conn, "test_user", "custom_table")


def test_run_drop_creates_connection_when_not_injected():
    """run_drop creates a HANA connection from config when none is injected."""
    from main import run_drop

    mock_conn = Mock()
    with (
        patch("main.create_hana_connection", return_value=mock_conn) as mock_create,
        patch("main.drop_table") as mock_drop,
        patch("main.DATABASE_URL", "hana.example.com"),
        patch("main.DATABASE_PORT", 443),
        patch("main.DATABASE_USER", "test_user"),
        patch("main.DATABASE_PASSWORD", "secret"),
    ):
        run_drop()

    mock_create.assert_called_once_with("hana.example.com", 443, "test_user", "secret")
    mock_drop.assert_called_once()


def test_run_drop_raises_when_connection_fails():
    """run_drop raises RuntimeError when the HANA connection cannot be established."""
    from main import run_drop

    with (
        patch("main.create_hana_connection", return_value=None),
        patch("main.drop_table") as mock_drop,
    ):
        with pytest.raises(RuntimeError, match="Failed to connect to the database"):
            run_drop()

    mock_drop.assert_not_called()


def test_run_list_tables_calls_list_tables_with_injected_connection(mock_hana_conn):
    """run_list_tables calls list_tables with the injected connection and DATABASE_USER."""
    from main import run_list_tables

    with (
        patch("main.list_tables", return_value=[]) as mock_list,
        patch("main.DATABASE_USER", "test_user"),
    ):
        run_list_tables(hana_conn=mock_hana_conn)

    mock_list.assert_called_once_with(mock_hana_conn, "test_user")


def test_run_list_tables_raises_when_connection_fails():
    """run_list_tables raises RuntimeError when the HANA connection cannot be established."""
    from main import run_list_tables

    with (
        patch("main.create_hana_connection", return_value=None),
        patch("main.list_tables") as mock_list,
    ):
        with pytest.raises(RuntimeError, match="Failed to connect to the database"):
            run_list_tables()

    mock_list.assert_not_called()
