"""Integration tests for main.py entry points.

These tests exercise the exact code paths used in production to catch
wiring bugs (e.g. passing deployment_id instead of model name).
"""

import os
from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings

from utils.models import create_embedding_factory, openai_embedding_creator
from utils.settings import EMBEDDING_MODEL_NAME, get_embedding_model_config


@pytest.fixture(scope="module")
def require_credentials():
    """Fail fast if the config file is not present."""
    default_config_path = Path(__file__).parent.parent.parent.parent / "config" / "config.json"
    config_path = Path(os.getenv("CONFIG_PATH", str(default_config_path)))
    if not config_path.exists():
        pytest.fail(f"Config file not found at {config_path}.")


@pytest.mark.integration
def test_run_indexer_embedding_model_creation(require_credentials):
    """Validate the exact model creation sequence used in run_indexer().

    Reproduces the production code path:
        embedding_model = get_embedding_model_config(EMBEDDING_MODEL_NAME)
        create_embedding = create_embedding_factory(openai_embedding_creator)
        embeddings_model = create_embedding(embedding_model.name)

    This catches bugs where e.g. embedding_model.deployment_id is passed
    instead of embedding_model.name, which causes:
        ValueError: Model '<deployment_id>' not found in config file.
    """
    # Mirrors run_indexer() exactly, minus DB and indexer setup.
    embedding_model_config = get_embedding_model_config(EMBEDDING_MODEL_NAME)
    create_embedding = create_embedding_factory(openai_embedding_creator)
    embeddings_model = create_embedding(embedding_model_config.name)

    assert isinstance(embeddings_model, Embeddings)

    # Verify it can actually produce embeddings (real API call).
    result = embeddings_model.embed_query("test")
    assert isinstance(result, list)
    assert len(result) > 0
    assert all(isinstance(x, float) for x in result)


@pytest.mark.integration
def test_run_indexer_fails_when_deployment_id_passed_as_model_name(require_credentials):
    """Passing deployment_id instead of model name must raise ValueError.

    This is the negative counterpart to test_run_indexer_embedding_model_creation.
    It documents and enforces that deployment IDs are not valid model names,
    so any regression that passes deployment_id will be caught by both tests.
    """
    embedding_model_config = get_embedding_model_config(EMBEDDING_MODEL_NAME)
    create_embedding = create_embedding_factory(openai_embedding_creator)

    with pytest.raises(ValueError, match="not found in config file"):
        create_embedding(embedding_model_config.deployment_id)
