from unittest.mock import patch

import pytest

from utils.config import Config, ModelConfig
from utils.models.anthropic import AnthropicModel
from utils.models.exceptions import ModelNotFoundError, UnsupportedModelError
from utils.models.factory import (
    ModelFactory,
    OpenAIModel,
)

SUPPORTED_MODEL_COUNT = 3

# Fixed model names for the factory test. Kept hardcoded here so the test is
# independent of `utils.settings.MAIN_MODEL_*` values, which are driven by
# `config/config.json` and may change over time.
TEST_GPT_MODEL_NAME = "gpt-4.1-mini"
TEST_ANTHROPIC_MODEL_NAME = "anthropic--claude-4.5-sonnet"
TEST_UNSUPPORTED_MODEL_NAME = "unsupported_model"


@pytest.fixture
def mock_config():
    """Override the project-wide `mock_config` fixture with a fixed model list
    so this test does not depend on environment / settings values."""
    return Config(
        models=[
            ModelConfig(name=TEST_GPT_MODEL_NAME, deployment_id="dep1", temperature=0),
            ModelConfig(name=TEST_ANTHROPIC_MODEL_NAME, deployment_id="dep2", temperature=0),
            ModelConfig(name=TEST_UNSUPPORTED_MODEL_NAME, deployment_id="dep3", temperature=0),
        ]
    )


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

    @pytest.fixture
    def mock_anthropic_model(self):
        with patch("utils.models.factory.AnthropicModel") as mock:
            yield mock

    @pytest.mark.parametrize(
        "test_case,model_name,expected_model_class,expected_exception",
        [
            (
                "should return OpenAIModel when gpt4o is requested",
                TEST_GPT_MODEL_NAME,
                OpenAIModel,
                None,
            ),
            (
                "should return AnthropicModel when an anthropic model is requested",
                TEST_ANTHROPIC_MODEL_NAME,
                AnthropicModel,
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
                TEST_UNSUPPORTED_MODEL_NAME,
                None,
                UnsupportedModelError,
            ),
        ],
    )
    def test_create_model(
        self,
        mock_openai_model,
        mock_gemini_model,
        mock_anthropic_model,
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
            elif expected_model_class == AnthropicModel:
                mock_anthropic_model.assert_called_once()
                assert model == mock_anthropic_model.return_value
            else:
                mock_gemini_model.assert_called_once()
                assert model == mock_gemini_model.return_value
