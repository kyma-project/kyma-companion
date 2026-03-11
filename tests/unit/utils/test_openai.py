from unittest.mock import patch

import pytest

from utils.config import ModelConfig
from utils.models.openai import OpenAIModel

TEST_MODEL_NAME = "test-openai-model"
TEST_DEPLOYMENT_ID = "test-deployment-id"


@pytest.fixture
def openai_model(mock_get_proxy_client):
    config = ModelConfig(name=TEST_MODEL_NAME, deployment_id=TEST_DEPLOYMENT_ID, temperature=0.7, type="openai")
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

    @pytest.mark.parametrize("reasoning_effort", ["low", "medium", "high"])
    def test_init_forwards_reasoning_effort(self, mock_get_proxy_client, reasoning_effort):
        config = ModelConfig(
            name=TEST_MODEL_NAME,
            deployment_id=TEST_DEPLOYMENT_ID,
            temperature=0.0,
            reasoning_effort=reasoning_effort,
        )
        with patch("utils.models.openai.ChatOpenAI") as mock_chat_openai:
            OpenAIModel(config, mock_get_proxy_client)

            _, kwargs = mock_chat_openai.call_args
            assert kwargs["reasoning_effort"] == reasoning_effort

    def test_init_omits_reasoning_effort_when_not_set(self, mock_get_proxy_client):
        config = ModelConfig(name=TEST_MODEL_NAME, deployment_id=TEST_DEPLOYMENT_ID, temperature=0.0)
        with patch("utils.models.openai.ChatOpenAI") as mock_chat_openai:
            OpenAIModel(config, mock_get_proxy_client)

            _, kwargs = mock_chat_openai.call_args
            assert "reasoning_effort" not in kwargs
