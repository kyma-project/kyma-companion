from unittest.mock import MagicMock, patch

import pytest

from utils.config import Config, ModelConfig
from utils.models import create_model, get_model, get_model_config


@pytest.fixture
def mock_config():
    return Config(
        models=[
            ModelConfig(name="model1", deployment_id="dep1"),
            ModelConfig(name="model2", deployment_id="dep2"),
        ]
    )


@pytest.mark.parametrize(
    "model_name, expected_deployment_id",
    [("model1", "dep1"), ("model2", "dep2"), ("non_existent_model", None)],
)
def test_get_model(mocker, mock_config, model_name, expected_deployment_id):
    with patch("utils.models.get_config", return_value=mock_config):
        result = get_model_config(model_name)
        if expected_deployment_id:
            assert result.name == model_name
            assert result.deployment_id == expected_deployment_id
        else:
            assert result is None


@pytest.mark.parametrize(
    "model_name, temperature, deployment_id",
    [
        ("model1", 0, "dep1"),
        ("model2", 0.5, "dep2"),
    ],
)
def test_create_llm(mock_config, model_name, temperature, deployment_id):
    mock_proxy_client = MagicMock()
    with (
        patch("utils.models.get_config", return_value=mock_config),
        patch("utils.models.get_proxy_client", return_value=mock_proxy_client),
        patch("utils.models.ChatOpenAI") as mock_chat_openai,
    ):
        create_model(model_name, temperature)

        mock_chat_openai.assert_called_once_with(
            deployment_id=deployment_id,
            proxy_client=mock_proxy_client,
            temperature=temperature,
        )


mock_llm1, mock_llm2 = MagicMock(), MagicMock()


@pytest.mark.parametrize(
    "model_name, llms, expected_llm",
    [
        ("model1", {"model1": mock_llm1}, mock_llm1),
        ("model2", {"model1": mock_llm1, "model2": mock_llm2}, mock_llm2),
        ("model3", {"model1": mock_llm1, "model2": mock_llm2}, None),
    ],
)
def test_get_llms(mocker, model_name, llms, expected_llm):
    mocker.patch("utils.models.llms", llms)
    result = get_model(model_name)
    assert result == expected_llm
