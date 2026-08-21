from unittest.mock import MagicMock, patch

import pytest

from utils.config import ModelConfig
from utils.models.openai import OpenAIModel


@pytest.fixture
def openai_model():
    config = ModelConfig(name="gpt-4", deployment_id="deployment-123", temperature=0.7)
    mock_client = MagicMock()
    with patch("utils.models.openai.OpenAIAdapter") as mock_adapter_cls:
        mock_adapter = MagicMock()
        mock_adapter_cls.return_value = mock_adapter
        model = OpenAIModel(config, mock_client)
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
