"""End-to-end tests for main.py entry points.

These tests run against live external services (SAP AI Core + Hana DB)
and write data to the database. They are kept separate from integration
tests so they can run as an independent CI job.
"""

import logging
from pathlib import Path

import pytest

from utils.models import create_embedding_factory, openai_embedding_creator
from utils.settings import (
    DATABASE_USER,
    EMBEDDING_MODEL_NAME,
    get_embedding_model_config,
)

E2E_DOCS_PATH = str(Path(__file__).parent.parent / "integration" / "fixtures" / "e2e_docs" / "kyma-docs")


@pytest.mark.e2e
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
