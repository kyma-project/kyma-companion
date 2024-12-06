from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from utils.config import Config, ModelConfig, get_config


@pytest.mark.parametrize(
    "json_content, expected_config",
    [
        (
            # Given: multiple models, two variables
            # Expected: Config object with two models, no variables
            """
            {
                "VARIABLE_NAME": "value",
                "VARIABLE_NAME2": "value2",
                "models": [
                    {
                        "name": "model1",
                        "deployment_id": "dep1",
                        "temperature": 0.0
                    },
                    {
                        "name": "model2",
                        "deployment_id": "dep2",
                        "temperature": 0.5
                    }
                ]
            }
            """,
            Config(
                models=[
                    ModelConfig(name="model1", deployment_id="dep1", temperature=0.0),
                    ModelConfig(name="model2", deployment_id="dep2", temperature=0.5),
                ]
            ),
        ),
        (
            # Given: single model, one variable
            # Expected: Config object with one model, no variable
            """
            {
                "VARIABLE_NAME": "value",
                "models": [
                    {
                        "name": "single_model",
                        "deployment_id": "single_dep",
                        "temperature": 1
                    }
                ]
            }
            """,
            Config(
                models=[
                    ModelConfig(
                        name="single_model", deployment_id="single_dep", temperature=1
                    )
                ]
            ),
        ),
        (
            # Given: no models, one variable
            # Expected: Config object with no models, no variables
            """
            {
                "VARIABLE_NAME": "value",
                "models": []
            }
            """,
            Config(models=[]),
        ),
    ],
)
def test_get_config(json_content, expected_config):
    # Mock `Path.is_file` to always return True for the config file
    with patch.object(Path, "open", mock_open(read_data=json_content)), patch.object(
        Path, "is_file", return_value=True
    ):
        result = get_config()
        assert result == expected_config
