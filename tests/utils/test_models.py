from unittest.mock import MagicMock, Mock, patch

import pytest

from utils.config import Config, ModelConfig
from utils.models import LLM, GeminiModel, ModelFactory, OpenAIModel, get_model_config


@pytest.fixture
def mock_config():
    return Config(
        models=[
            ModelConfig(name=LLM.GPT4O_MODEL, deployment_id="dep1", temperature=0),
            ModelConfig(name=LLM.GPT35_MODEL, deployment_id="dep2", temperature=0),
            ModelConfig(name=LLM.GEMINI_10_PRO, deployment_id="dep3", temperature=0),
        ]
    )


@pytest.fixture
def mock_get_proxy_client():
    with patch("utils.models.get_proxy_client") as mock_get_proxy_client:
        mock_proxy_client = MagicMock()
        mock_get_proxy_client.return_value = mock_proxy_client
        yield mock_proxy_client


@pytest.fixture
def mock_get_config(mock_config):
    with patch("utils.models.get_config", return_value=mock_config):
        yield


@pytest.mark.parametrize(
    "model_name, expected_deployment_id",
    [
        (LLM.GPT4O_MODEL, "dep1"),
        (LLM.GPT35_MODEL, "dep2"),
        (LLM.GEMINI_10_PRO, "dep3"),
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


@pytest.fixture
def gemini_model(mock_get_proxy_client):
    config = ModelConfig(name="gemini-1.0-pro", deployment_id="dep2", temperature=0)
    with patch("utils.models.GenerativeModel") as mock_generative_model:
        model = GeminiModel(config, mock_get_proxy_client)
        model._model = mock_generative_model.return_value
        return model


class TestGeminiModel:
    def test_gemini_model_invoke(self, gemini_model):
        test_content = "Hello, world!"
        expected_response = Mock()
        expected_response.text = "Hello, Kyma user!"
        gemini_model._model.generate_content.return_value = expected_response

        result = gemini_model.invoke(test_content)

        expected_content = [{"role": "user", "parts": [{"text": test_content}]}]
        gemini_model._model.generate_content.assert_called_once_with(expected_content)
        assert result == expected_response


class TestModelFactory:

    @pytest.fixture
    def mock_generative_model(self):
        with patch("utils.models.GenerativeModel") as mock_generative_model:
            yield mock_generative_model

    @pytest.fixture
    def model_factory(self, mock_get_proxy_client):
        return ModelFactory()

    @pytest.mark.parametrize(
        "model_name, expected_result",
        [
            (LLM.GPT4O_MODEL, OpenAIModel),
            (LLM.GPT35_MODEL, OpenAIModel),
            (LLM.GEMINI_10_PRO, GeminiModel),
            ("non_existent_model", ValueError),
        ],
    )
    def test_create_model(
        self,
        mock_get_config,
        mock_generative_model,
        model_factory,
        model_name,
        expected_result,
    ):
        if expected_result == ValueError:
            with pytest.raises(
                ValueError,
                match=f"Model {model_name} not found in the configuration.",
            ):
                model_factory.create_model(model_name)
        else:
            model = model_factory.create_model(model_name)
            assert isinstance(model, expected_result)
            assert model.name == model_name

    @pytest.mark.parametrize(
        "model_name, expected_model",
        [
            (LLM.GPT4O_MODEL, OpenAIModel),
            (LLM.GEMINI_10_PRO, GeminiModel),
            ("non_existent_model", type(None)),
        ],
    )
    def test_get_model(
        self,
        mock_get_config,
        mock_generative_model,
        model_factory,
        model_name,
        expected_model,
    ):
        # First, create the models
        if model_name != "non_existent_model":
            model_factory.create_model(model_name)

        # Then, test get_model
        result = model_factory.get_model(model_name)
        assert isinstance(result, expected_model)
