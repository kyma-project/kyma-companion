from unittest.mock import patch

import pytest

from utils.models.exceptions import ModelNotFoundError, UnsupportedModelError
from utils.models.factory import (
    ModelFactory,
    OpenAIModel,
)

SUPPORTED_MODEL_COUNT = 3


@pytest.fixture
def model_factory(mock_get_proxy_client, mock_config):
    return ModelFactory(mock_config)


class TestModelFactory:
    @pytest.fixture
    def mock_openai_model(self):
        with patch("utils.models.factory.OpenAIModel") as mock:
            yield mock

    @pytest.fixture
    def mock_gemini_model(self):
        with patch("utils.models.factory.GeminiModel") as mock:
            yield mock

    @pytest.mark.parametrize(
        "test_case,model_name,expected_model_class,expected_exception",
        [
            (
                "should return OpenAIModel when gpt4o is requested",
                "gpt-4.1",
                OpenAIModel,
                None,
            ),
            (
                "should raise error when non_existent_model is requested",
                "non_existent_model",
                None,
                ModelNotFoundError,
            ),
            (
                "should raise error when unsupported model is requested",
                "unsupported_model",
                None,
                UnsupportedModelError,
            ),
        ],
    )
    def test_create_model(
        self,
        mock_openai_model,
        mock_gemini_model,
        model_factory,
        test_case,
        model_name,
        expected_model_class,
        expected_exception,
    ):
        if expected_exception:
            with pytest.raises(expected_exception):
                model_factory.create_model(model_name)
        else:
            model = model_factory.create_model(model_name)

            if expected_model_class == OpenAIModel:
                mock_openai_model.assert_called_once()
                assert model == mock_openai_model.return_value
            else:
                mock_gemini_model.assert_called_once()
                assert model == mock_gemini_model.return_value
