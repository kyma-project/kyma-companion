"""Integration tests for main.py entry points.

These tests exercise the exact code paths used in production to catch
wiring bugs (e.g. passing deployment_id instead of model name).
"""

import logging
from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings

from utils.models import create_embedding_factory, openai_embedding_creator
from utils.settings import (
    DATABASE_USER,
    EMBEDDING_MODEL_NAME,
    get_embedding_model_config,
)

E2E_DOCS_PATH = str(Path(__file__).parent / "fixtures" / "e2e_docs" / "kyma-docs")


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

    with pytest.raises(ValueError, match="not found in the configuration"):
        create_embedding(embedding_model_config.deployment_id)


@pytest.mark.integration
def test_run_indexer_e2e(hana_conn, e2e_table_name):
    """End-to-end test that mirrors run_indexer() against a real Hana DB table.

    Follows the exact production code path:
        1. get_embedding_model_config() -> ModelConfig
        2. create_embedding_factory(openai_embedding_creator) -> factory
        3. factory(embedding_model.name) -> real embeddings model
        4. create_hana_connection() -> real DB connection
        5. AdaptiveSplitMarkdownIndexer(docs_path, ...).index() -> chunks stored in Hana

    Verifies that chunks from the test documents are stored in the table,
    then drops the table on teardown.
    """
    from indexing.adaptive_indexer import AdaptiveSplitMarkdownIndexer

    # Step 1-3: model creation — exact run_indexer() sequence.
    embedding_model_config = get_embedding_model_config(EMBEDDING_MODEL_NAME)
    create_embedding = create_embedding_factory(openai_embedding_creator)
    embeddings_model = create_embedding(embedding_model_config.name)

    # Step 4-5: index test documents into the e2e table.
    indexer = AdaptiveSplitMarkdownIndexer(E2E_DOCS_PATH, embeddings_model, hana_conn, e2e_table_name)
    try:
        indexer.index()

        # Verify chunks were written to the table.
        cursor = hana_conn.cursor()
        cursor.execute(f'SELECT COUNT(*) FROM "{DATABASE_USER}"."{e2e_table_name}"')
        count = cursor.fetchone()[0]
        cursor.close()

        assert count > 0, f"Expected chunks in table '{e2e_table_name}', but found none."
    finally:
        # Drop the test table regardless of test outcome.
        try:
            cursor = hana_conn.cursor()
            cursor.execute(f'DROP TABLE "{DATABASE_USER}"."{e2e_table_name}"')
            cursor.close()
            logging.info(f"Dropped e2e test table '{e2e_table_name}'.")
        except Exception:
            logging.exception(f"Failed to drop e2e test table '{e2e_table_name}'.")
