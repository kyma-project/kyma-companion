from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def root_tests_path():
    """Return the path to the fixtures directory"""
    return Path(__file__).parent
