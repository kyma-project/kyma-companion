from unittest.mock import patch

import pytest

from utils.config import ModelConfig
from utils.models.openai import OpenAIModel


@pytest.fixture
def openai_model(mock_get_proxy_client):
    config = ModelConfig(
        name="gpt-4", deployment_id="deployment-123", temperature=0.7, type="openai"
    )
    with patch("utils.models.openai.ChatOpenAI") as mock_chat_openai:
        model = OpenAIModel(config, mock_get_proxy_client)
        model._llm = mock_chat_openai.return_value
        return model


class TestOpenAIModel:
    """Test suite for OpenAIModel class."""

    def test_invoke(self, openai_model):
        # When
        test_content = "Hello, world!"
        expected_response = "Hello, Kyma user!"
        openai_model._llm.invoke.return_value = expected_response

        result = openai_model.invoke(test_content)

        # Then
        openai_model._llm.invoke.assert_called_once_with(test_content)
        assert result == expected_response
