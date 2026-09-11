"""Integration tests for main.py entry points.

These tests exercise the exact code paths used in production to catch
wiring bugs (e.g. passing deployment_id instead of model name).
"""

import logging
from pathlib import Path
from unittest.mock import patch

import pytest
from langchain_core.embeddings import Embeddings
from utils.hana import drop_table, list_tables

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

    Also asserts that no leftover staging tables remain after a successful run.
    """
    from indexing.adaptive_indexer import AdaptiveSplitMarkdownIndexer

    # Step 1-3: model creation -- exact run_indexer() sequence.
    embedding_model_config = get_embedding_model_config(EMBEDDING_MODEL_NAME)
    create_embedding = create_embedding_factory(openai_embedding_creator)
    embeddings_model = create_embedding(embedding_model_config.name)

    # Step 4-5: index test documents into the e2e table.
    indexer = AdaptiveSplitMarkdownIndexer(E2E_DOCS_PATH, embeddings_model, hana_conn, e2e_table_name)
    staging_name = indexer.staging_table_name
    try:
        indexer.index()

        # Verify chunks were written to the table.
        cursor = hana_conn.cursor()
        cursor.execute(f'SELECT COUNT(*) FROM "{DATABASE_USER}"."{e2e_table_name}"')
        count = cursor.fetchone()[0]
        cursor.close()

        assert count > 0, f"Expected chunks in table '{e2e_table_name}', but found none."

        # Verify no leftover staging table remains.
        table_names = {row[0] for row in list_tables(hana_conn, DATABASE_USER)}
        assert staging_name not in table_names, (
            f"Staging table '{staging_name}' was not cleaned up after successful index run."
        )
    finally:
        # Drop the test table regardless of test outcome.
        for name in (e2e_table_name, staging_name):
            drop_table(hana_conn, DATABASE_USER, name)
            logging.info(f"Dropped e2e test table '{name}' (if it existed).")


@pytest.mark.integration
def test_run_indexer_e2e_failing_batch_leaves_live_table_intact(hana_conn, e2e_table_name):
    """When add_documents raises mid-batch, the live table must remain untouched.

    This exercises the failure path introduced by the atomic-swap implementation:
    on error, staging is dropped and the live table is never renamed.
    """
    from indexing.adaptive_indexer import AdaptiveSplitMarkdownIndexer

    embedding_model_config = get_embedding_model_config(EMBEDDING_MODEL_NAME)
    create_embedding = create_embedding_factory(openai_embedding_creator)
    embeddings_model = create_embedding(embedding_model_config.name)

    # Seed the live table with known content via a successful run first.
    seeder = AdaptiveSplitMarkdownIndexer(E2E_DOCS_PATH, embeddings_model, hana_conn, e2e_table_name)
    seeder_staging = seeder.staging_table_name
    try:
        seeder.index()
    finally:
        drop_table(hana_conn, DATABASE_USER, seeder_staging)

    cursor = hana_conn.cursor()
    cursor.execute(f'SELECT COUNT(*) FROM "{DATABASE_USER}"."{e2e_table_name}"')
    original_count = cursor.fetchone()[0]
    cursor.close()
    assert original_count > 0, "Pre-condition: live table must be non-empty before the failing run."

    # Now attempt a second run that will fail mid-batch.
    failing_indexer = AdaptiveSplitMarkdownIndexer(E2E_DOCS_PATH, embeddings_model, hana_conn, e2e_table_name)
    failing_staging = failing_indexer.staging_table_name

    call_count = {"n": 0}
    original_add = failing_indexer.db.add_documents

    def add_documents_failing(docs):  # type: ignore[no-untyped-def]
        call_count["n"] += 1
        if call_count["n"] >= 1:
            raise RuntimeError("simulated batch failure")
        return original_add(docs)

    try:
        with (
            patch.object(failing_indexer.db, "add_documents", side_effect=add_documents_failing),
            pytest.raises(RuntimeError, match="simulated batch failure"),
        ):
            failing_indexer.index()

        # Live table must be untouched.
        cursor = hana_conn.cursor()
        cursor.execute(f'SELECT COUNT(*) FROM "{DATABASE_USER}"."{e2e_table_name}"')
        count_after = cursor.fetchone()[0]
        cursor.close()
        assert count_after == original_count, (
            f"Live table was modified during a failing run: expected {original_count} rows, got {count_after}."
        )

        # Staging table must not exist.
        table_names = {row[0] for row in list_tables(hana_conn, DATABASE_USER)}
        assert failing_staging not in table_names, (
            f"Staging table '{failing_staging}' was not cleaned up after a failed run."
        )
    finally:
        for name in (e2e_table_name, failing_staging):
            drop_table(hana_conn, DATABASE_USER, name)
            logging.info(f"Dropped e2e test table '{name}' (if it existed).")
