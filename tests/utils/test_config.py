from unittest.mock import mock_open, patch

import pytest

from utils.config import Config, Model, get_config


@pytest.mark.parametrize("yaml_content, expected_config", [
    (
            """
            models:
              - name: model1
                deployment_id: dep1
              - name: model2
                deployment_id: dep2
            """,
            Config(models=[
                Model(name="model1", deployment_id="dep1"),
                Model(name="model2", deployment_id="dep2")
            ])
    ),
    (
            """
            models:
              - name: single_model
                deployment_id: single_dep
            """,
            Config(models=[
                Model(name="single_model", deployment_id="single_dep")
            ])
    ),
    (
            """
            models: []
            """,
            Config(models=[])
    )
])
def test_get_config(yaml_content, expected_config):
    with patch("builtins.open", mock_open(read_data=yaml_content)):
        result = get_config()
        assert result == expected_config
