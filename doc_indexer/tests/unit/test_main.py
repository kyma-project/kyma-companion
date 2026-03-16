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


def test_run_indexer_passes_model_name_not_deployment_id(mock_embedding_model_config):
    """Ensure run_indexer passes the model name (not deployment_id) to create_embedding.

    Regression test for: ValueError: Model '<deployment_id>' not found in config file.
    """
    mock_embeddings = Mock()
    mock_create_embedding = Mock(return_value=mock_embeddings)
    mock_factory = Mock(return_value=mock_create_embedding)
    mock_hana_conn = Mock()
    mock_indexer = Mock()

    with (
        patch("main.get_embedding_model_config", return_value=mock_embedding_model_config),
        patch("main.create_embedding_factory", return_value=mock_factory),
        patch("main.openai_embedding_creator"),
        patch("main.create_hana_connection", return_value=mock_hana_conn),
        patch("main.AdaptiveSplitMarkdownIndexer", return_value=mock_indexer),
    ):
        from main import run_indexer

        run_indexer()

    # The embedding factory must be called with the model name, not the deployment ID.
    mock_factory.assert_called_once_with(EMBEDDING_MODEL_NAME)
    assert mock_factory.call_args[0][0] != EMBEDDING_DEPLOYMENT_ID, (
        "run_indexer passed deployment_id instead of model name to create_embedding"
    )
