from unittest.mock import MagicMock, patch

import pytest

from utils.config import Config, ModelConfig
from utils.models.factory import (
    ModelType,
)


@pytest.fixture
def mock_config():
    return Config(
        models=[
            ModelConfig(name=ModelType.GPT4O, deployment_id="dep1", temperature=0),
            ModelConfig(name=ModelType.GPT35, deployment_id="dep2", temperature=0),
            ModelConfig(
                name=ModelType.GEMINI_10_PRO, deployment_id="dep3", temperature=0
            ),
        ]
    )


@pytest.fixture
def mock_get_proxy_client():
    with patch("utils.models.factory.get_proxy_client") as mock_get_proxy_client:
        mock_proxy_client = MagicMock()
        mock_get_proxy_client.return_value = mock_proxy_client
        yield mock_proxy_client


@pytest.fixture
def mock_get_config(mock_config):
    with patch("utils.models.factory.get_config", return_value=mock_config):
        yield
