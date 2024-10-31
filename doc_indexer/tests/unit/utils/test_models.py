from unittest.mock import Mock, patch

import pytest
from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.langchain.openai import OpenAIEmbeddings
from langchain_core.embeddings import Embeddings

from utils.models import (
    create_embedding_factory,
    init_proxy_client,
    openai_embedding_creator,
)


@pytest.fixture(autouse=True)
def clear_lru_cache():
    """Clear the LRU cache before each test."""
    yield
    init_proxy_client.cache_clear()


@pytest.fixture
def mock_proxy_client():
    return Mock(spec=BaseProxyClient)


@pytest.fixture
def mock_get_proxy_client():
    with patch("utils.models.get_proxy_client") as mock:
        yield mock


@pytest.mark.parametrize(
    "test_case,mock_return,expected_exception,expected_error_msg",
    [
        (
            "successful initialization",
            Mock(spec=BaseProxyClient),
            None,
            None,
        ),
        (
            "initialization error",
            Exception("Connection error"),
            Exception,
            "Connection error",
        ),
    ],
)
def test_init_proxy_client(
    mock_get_proxy_client,
    clear_lru_cache,
    test_case,
    mock_return,
    expected_exception,
    expected_error_msg,
):
    # Arrange
    if isinstance(mock_return, Exception):
        mock_get_proxy_client.side_effect = mock_return
    else:
        mock_get_proxy_client.return_value = mock_return

    # Act & Assert
    if expected_exception:
        with pytest.raises(expected_exception) as exc_info:
            init_proxy_client()
        assert str(exc_info.value) == expected_error_msg
    else:
        result = init_proxy_client()
        assert isinstance(result, Mock)
        assert mock_get_proxy_client.return_value == result

    mock_get_proxy_client.assert_called_once_with("gen-ai-hub")


@pytest.mark.parametrize(
    "test_case,deployment_id,creator_return,init_client_error,expected_exception",
    [
        (
            "successful factory creation",
            "test-deployment",
            Mock(spec=Embeddings),
            None,
            None,
        ),
        (
            "factory creation with creator error",
            "test-deployment",
            Exception("Creator error"),
            None,
            Exception,
        ),
        (
            "factory creation with client initialization error",
            "test-deployment",
            Mock(spec=Embeddings),
            Exception("Client init error"),
            Exception,
        ),
    ],
)
def test_create_embedding_factory(
    mock_get_proxy_client,
    mock_proxy_client,
    test_case,
    deployment_id,
    creator_return,
    init_client_error,
    expected_exception,
):
    # Arrange
    if init_client_error:
        mock_get_proxy_client.side_effect = init_client_error
    else:
        mock_get_proxy_client.return_value = mock_proxy_client

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
        mock_embedding_creator.assert_called_once_with(deployment_id, mock_proxy_client)

    # Verify init_proxy_client was called (which internally calls get_proxy_client)
    mock_get_proxy_client.assert_called_once_with("gen-ai-hub")


@pytest.mark.parametrize(
    "test_case,deployment_id,mock_openai,expected_exception,expected_error_msg",
    [
        (
            "successful creation",
            "test-deployment",
            None,
            None,
            None,
        ),
        (
            "creation error",
            "test-deployment",
            Exception("Model creation error"),
            Exception,
            "Model creation error",
        ),
    ],
)
def test_openai_embedding_creator(
    mock_proxy_client,
    test_case,
    deployment_id,
    mock_openai,
    expected_exception,
    expected_error_msg,
):
    # Arrange
    if mock_openai:
        with patch("utils.models.OpenAIEmbeddings", side_effect=mock_openai):
            # Act & Assert
            with pytest.raises(expected_exception) as exc_info:
                openai_embedding_creator(deployment_id, mock_proxy_client)
            assert str(exc_info.value) == expected_error_msg
    else:
        # Act
        result = openai_embedding_creator(deployment_id, mock_proxy_client)

        # Assert
        assert isinstance(result, OpenAIEmbeddings)
        assert result.proxy_client == mock_proxy_client
