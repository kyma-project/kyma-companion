from unittest.mock import Mock, patch

import pytest
from langchain_core.embeddings import Embeddings
from utils.model_config import ModelConfig

from utils.models import (
    create_embedding_factory,
    openai_embedding_creator,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "test_case,deployment_id,creator_return,expected_exception",
    [
        (
            "successful factory creation",
            "test-deployment",
            Mock(spec=Embeddings),
            None,
        ),
        (
            "factory creation with creator error",
            "test-deployment",
            Exception("Creator error"),
            Exception,
        ),
    ],
)
def test_create_embedding_factory(
    test_case,
    deployment_id,
    creator_return,
    expected_exception,
):
    # Arrange
    mock_embedding_creator = Mock()
    if isinstance(creator_return, Exception):
        mock_embedding_creator.side_effect = creator_return
    else:
        mock_embedding_creator.return_value = creator_return

    # Act & Assert
    factory = create_embedding_factory(mock_embedding_creator)

    if expected_exception:
        with pytest.raises(expected_exception):
            factory(deployment_id)
    else:
        result = factory(deployment_id)
        assert isinstance(result, Mock)
        assert result == creator_return
        mock_embedding_creator.assert_called_once_with(deployment_id)


@pytest.mark.parametrize(
    "test_case,model_name,mock_error",
    [
        (
            "successful creation",
            "text-embedding-3-large",
            None,
        ),
        (
            "creation error",
            "text-embedding-3-large",
            ValueError("Model creation error"),
        ),
    ],
)
def test_openai_embedding_creator(
    test_case,
    model_name,
    mock_error,
    caplog,
):
    # Arrange
    mock_embeddings = Mock(spec=Embeddings)
    mock_model_config = ModelConfig(name=model_name, deployment_id="test-deployment-id")

    with (
        patch("utils.models.get_embedding_model_config", return_value=mock_model_config),
        patch("utils.models.AICoreClient") as mock_client_cls,
        patch("utils.models.make_openai_embeddings") as mock_make,
        patch("utils.models.time.sleep"),
    ):
        mock_client = Mock()
        mock_client_cls.return_value = mock_client

        if mock_error:
            mock_make.side_effect = mock_error
        else:
            mock_make.return_value = mock_embeddings

        # Act & Assert
        if mock_error:
            with pytest.raises(type(mock_error)) as exc_info:
                openai_embedding_creator(model_name)
            assert str(exc_info.value) == str(mock_error)
            assert "Error while creating OpenAI embedding model" in caplog.text
        else:
            result = openai_embedding_creator(model_name)

            assert result == mock_embeddings
            mock_make.assert_called_once_with(
                client=mock_client,
                deployment_id="test-deployment-id",
                model_name=model_name,
            )
