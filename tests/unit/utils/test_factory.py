from unittest.mock import patch

import pytest

from utils.models.exceptions import ModelNotFoundError
from utils.models.factory import (
    GeminiModel,
    ModelFactory,
    ModelType,
    OpenAIModel,
    get_model_config,
)


@pytest.mark.parametrize(
    "model_name, expected_deployment_id",
    [
        (ModelType.GPT4O, "dep1"),
        (ModelType.GPT35, "dep2"),
        (ModelType.GEMINI_10_PRO, "dep3"),
        ("non_existent_model", None),
    ],
)
def test_get_model_config(mock_get_config, model_name, expected_deployment_id):
    result = get_model_config(model_name)
    if expected_deployment_id:
        assert result.name == model_name
        assert result.deployment_id == expected_deployment_id
    else:
        assert result is None


class TestModelFactory:
    @pytest.fixture
    def mock_generative_model(self):
        with patch("utils.models.gemini.GenerativeModel") as mock_generative_model:
            yield mock_generative_model

    @pytest.fixture
    def model_factory(self, mock_get_proxy_client):
        return ModelFactory()

    @pytest.mark.parametrize(
        "test_case,model_name, expected_result, expected_exception",
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
        mock_generative_model,
        model_factory,
        test_case,
        model_name,
        expected_result,
        expected_exception,
    ):
        if expected_exception:
            # When exception is expected
            if expected_exception == ModelNotFoundError:
                with pytest.raises(expected_exception):
                    model_factory.create_model(model_name)

        else:
            # When
            model = model_factory.create_model(model_name)

            # Then
            assert isinstance(model, expected_result)
            assert model.name == model_name

    def test_create_models(
        self,
        mock_get_config,
        mock_generative_model,
        model_factory,
    ):
        # When
        models = model_factory.create_models()

        # Then
        assert isinstance(models[ModelType.GPT4O], OpenAIModel)
        assert isinstance(models[ModelType.GPT35], OpenAIModel)
        assert isinstance(models[ModelType.GEMINI_10_PRO], GeminiModel)

    @pytest.mark.parametrize(
        "test_case, model_name, expected_model",
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
                type(None),
            ),
        ],
    )
    def test_get_model(
        self,
        mock_get_config,
        mock_generative_model,
        model_factory,
        test_case,
        model_name,
        expected_model,
    ):
        if expected_model != type(None):
            # When
            model = model_factory.create_model(model_name)

            # Then
            assert isinstance(model, expected_model)
            assert model.name == model_name
        else:
            # When exception is expected
            with pytest.raises(ModelNotFoundError):
                model_factory.create_model(model_name)
