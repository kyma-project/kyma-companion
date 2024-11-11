from unittest.mock import MagicMock, Mock, patch

import pytest

from utils.config import Config, ModelConfig
from utils.models.factory import (
    ModelType,
    GeminiModel,
    ModelFactory,
    OpenAIModel,
    get_model_config,
)
from utils.models.exceptions import ModelNotFoundError, UnsupportedModelError

@pytest.fixture
def gemini_model(mock_get_proxy_client):
    config = ModelConfig(name="gemini-1.0-pro", deployment_id="dep2", temperature=0)
    with patch("utils.models.gemini.GenerativeModel") as mock_generative_model:
        model = GeminiModel(config, mock_get_proxy_client)
        model._model = mock_generative_model.return_value
        return model

class TestGeminiModel:
    def test_invoke(self, gemini_model):
        # When
        test_content = "Hello, world!"
        expected_response = Mock()
        expected_response.text = "Hello, Kyma user!"
        gemini_model._model.generate_content.return_value = expected_response

        result = gemini_model.invoke(test_content)

        # Then
        expected_content = [{"role": "user", "parts": [{"text": test_content}]}]
        gemini_model._model.generate_content.assert_called_once_with(expected_content)
        assert result == expected_response