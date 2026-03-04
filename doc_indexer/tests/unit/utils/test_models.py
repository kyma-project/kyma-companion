from unittest.mock import Mock, patch

import pytest
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

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
    "test_case,deployment_id,mock_openai_error",
    [
        (
            "successful creation",
            "test-deployment-id",
            None,
        ),
        (
            "creation error",
            "test-deployment-id",
            ValueError("Model creation error"),
        ),
    ],
)
def test_openai_embedding_creator(
    test_case,
    deployment_id,
    mock_openai_error,
    caplog,
):
    # Arrange
    mock_embeddings = Mock(spec=OpenAIEmbeddings)

    with patch("utils.models.OpenAIEmbeddings") as mock_openai_cls:
        if mock_openai_error:
            mock_openai_cls.side_effect = mock_openai_error
        else:
            mock_openai_cls.return_value = mock_embeddings

        # Act & Assert
        if mock_openai_error:
            with pytest.raises(type(mock_openai_error)) as exc_info:
                openai_embedding_creator(deployment_id)
            assert str(exc_info.value) == str(mock_openai_error)
            assert "Error while creating OpenAI embedding model" in caplog.text
        else:
            result = openai_embedding_creator(deployment_id)

            # Assert the result is correct
            assert result == mock_embeddings

            # Assert OpenAIEmbeddings was called with correct parameters
            mock_openai_cls.assert_called_once_with(
                model=deployment_id,
            )
