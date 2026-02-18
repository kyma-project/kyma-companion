from unittest.mock import Mock, patch

import pytest

from utils.config import ModelConfig
from utils.models.factory import (
    GeminiModel,
)


@pytest.fixture
def gemini_model(mock_get_proxy_client):
    config = ModelConfig(name="gemini-1.0-pro", deployment_id="dep2", temperature=0)
    with patch("utils.models.gemini.GoogleGenAIClient") as mock_client:
        model = GeminiModel(config, mock_get_proxy_client)
        model._model = mock_client.return_value
        return model


class TestGeminiModel:
    def test_invoke(self, gemini_model):
        # When
        test_content = "Hello, world!"
        expected_response = Mock()
        expected_response.text = "Hello, Kyma user!"
        gemini_model._model.models.generate_content.return_value = expected_response

        result = gemini_model.invoke(test_content)

        # Then
        gemini_model._model.models.generate_content.assert_called_once_with(
            model="gemini-1.0-pro",
            contents=test_content,
        )
        assert result == expected_response
