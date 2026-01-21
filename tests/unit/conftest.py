from unittest.mock import MagicMock, patch

import pytest

from utils.config import Config, ModelConfig
from utils.settings import (
    MAIN_EMBEDDING_MODEL_NAME,
    MAIN_MODEL_MINI_NAME,
    MAIN_MODEL_NAME,
)


@pytest.fixture
def mock_config():
    return Config(
        models=[
            ModelConfig(name=MAIN_MODEL_NAME, deployment_id="dep1", temperature=0),
            ModelConfig(name=MAIN_MODEL_MINI_NAME, deployment_id="dep2", temperature=0),
            ModelConfig(name=MAIN_EMBEDDING_MODEL_NAME, deployment_id="dep3", temperature=0),
            ModelConfig(name="unsupported_model", deployment_id="dep4", temperature=0),
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
