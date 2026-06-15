from unittest.mock import MagicMock, Mock, patch

import pytest
from aiohttp import ClientResponse

from utils.config import Config, ModelConfig
from utils.settings import (
    MAIN_EMBEDDING_MODEL_NAME,
    MAIN_MODEL_MINI_NAME,
    MAIN_MODEL_NAME,
)

# aioresponses 0.7.8 does not pass stream_writer to ClientResponse.__init__,
# which became required in aiohttp 3.14.0. Patch until aioresponses releases a fix.
_original_client_response_init = ClientResponse.__init__


def _patched_client_response_init(self, *args, **kwargs):
    if "stream_writer" not in kwargs:
        mock_stream_writer = Mock()
        mock_stream_writer.output_size = 0
        kwargs["stream_writer"] = mock_stream_writer
    _original_client_response_init(self, *args, **kwargs)


ClientResponse.__init__ = _patched_client_response_init


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
