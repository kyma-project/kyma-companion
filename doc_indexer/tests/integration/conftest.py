import pytest

from utils.settings import EMBEDDING_MODEL_NAME, get_embedding_model_config


@pytest.fixture(scope="module")
def require_credentials():
    """Fail fast if the config was not loaded or the embedding model is not configured."""
    try:
        get_embedding_model_config(EMBEDDING_MODEL_NAME)
    except Exception as e:
        pytest.fail(f"Credentials not available: {e}")
