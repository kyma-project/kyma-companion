"""Tests for INDEX_TO_FILE boolean parsing in settings."""

import importlib

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "env_value, expected",
    [
        ("false", False),
        ("False", False),
        ("FALSE", False),
        ("0", False),
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("1", True),
    ],
)
def test_index_to_file_bool_cast(monkeypatch, env_value, expected):
    """INDEX_TO_FILE must be parsed as a proper bool, not a non-empty-string truthy."""
    monkeypatch.setenv("INDEX_TO_FILE", env_value)
    import utils.settings as settings_module

    importlib.reload(settings_module)
    assert settings_module.INDEX_TO_FILE is expected
