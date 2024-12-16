from unittest.mock import Mock, patch

import pytest

from utils.models.exceptions import ModelNotFoundError
from utils.models.factory import (
    GeminiModel,
    ModelFactory,
    ModelType,
    OpenAIModel,
    get_model_config,
)

SUPPORTED_MODEL_COUNT = 3


@pytest.fixture
def mock_model_config():
    return Mock(name="test_model", deployment_id="test_deployment")


@pytest.mark.parametrize(
    "model_name, expected_deployment_id, expected_error",
    [
        (ModelType.GPT4O, "dep1", None),
        (ModelType.GPT35, "dep2", None),
        (ModelType.GEMINI_10_PRO, "dep3", None),
        ("non_existent_model", None, None),
        ("", None, None),
        (None, None, None),
    ],
)
def test_get_model_config(
    mock_get_config, model_name, expected_deployment_id, expected_error
):
    if expected_error:
        with pytest.raises(expected_error):
            get_model_config(model_name)
    else:
        result = get_model_config(model_name)
        if expected_deployment_id:
            assert result.name == model_name
            assert result.deployment_id == expected_deployment_id
        else:
            assert result is None


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
    def model_factory(self, mock_get_proxy_client):
        return ModelFactory()

    @pytest.mark.parametrize(
        "test_case,model_name,expected_model_class,expected_exception",
        [
            (
                "should return OpenAIModel when gpt4o is requested",
                ModelType.GPT4O,
                OpenAIModel,
                None,
            ),
            (
                "should return OpenAIModel when gpt35 is requested",
                ModelType.GPT35,
                OpenAIModel,
                None,
            ),
            (
                "should return GeminiModel when gemini_10_pro is requested",
                ModelType.GEMINI_10_PRO,
                GeminiModel,
                None,
            ),
            (
                "should raise error when non_existent_model is requested",
                "non_existent_model",
                None,
                ModelNotFoundError,
            ),
        ],
    )
    def test_create_model(
        self,
        mock_get_config,
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

    def test_create_models_returns_all_supported_models(
        self,
        mock_get_config,
        mock_openai_model,
        mock_gemini_model,
        model_factory,
    ):
        # When
        models = model_factory.create_models()

        # Then
        assert (
            len(models) == SUPPORTED_MODEL_COUNT
        )  # Verify we get all supported models

        # Verify correct model instances were created
        assert models[ModelType.GPT4O] == mock_openai_model.return_value
        assert models[ModelType.GPT35] == mock_openai_model.return_value
        assert models[ModelType.GEMINI_10_PRO] == mock_gemini_model.return_value

        # Verify each model has proper configuration
        for model in models.values():
            assert model.name is not None
            assert model.deployment_id is not None

    @pytest.mark.parametrize(
        "test_case,model_name,expected_model_class",
        [
            ("get gpt4o model should return OpenAIModel", ModelType.GPT4O, OpenAIModel),
            (
                "get gemini_10_pro model should return GeminiModel",
                ModelType.GEMINI_10_PRO,
                GeminiModel,
            ),
            (
                "get non_existent_model should raise error",
                "non_existent_model",
                None,
            ),
        ],
    )
    def test_get_model(
        self,
        mock_get_config,
        mock_openai_model,
        mock_gemini_model,
        model_factory,
        test_case,
        model_name,
        expected_model_class,
    ):
        if expected_model_class is None:
            with pytest.raises(ModelNotFoundError):
                model_factory.create_model(model_name)
        else:
            model = model_factory.create_model(model_name)

            if expected_model_class == OpenAIModel:
                mock_openai_model.assert_called_once()
                assert model == mock_openai_model.return_value
            else:
                mock_gemini_model.assert_called_once()
                assert model == mock_gemini_model.return_value
