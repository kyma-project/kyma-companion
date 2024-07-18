from unittest.mock import patch

import pytest

from utils.config import Config, Model
from utils.models import get_model


@pytest.fixture
def mock_config():
    return Config(models=[
        Model(name="model1", deployment_id="dep1"),
        Model(name="model2", deployment_id="dep2"),
    ])


@pytest.mark.parametrize("model_name, expected_deployment_id", [
    ("model1", "dep1"),
    ("model2", "dep2"),
    ("non_existent_model", None)
])
def test_get_model(mock_config, model_name, expected_deployment_id):
    with (patch('utils.config.load', return_value=mock_config)):
        result = get_model(model_name)
        if expected_deployment_id:
            assert result.name == model_name
            assert result.deployment_id == expected_deployment_id
        else:
            assert result is None
