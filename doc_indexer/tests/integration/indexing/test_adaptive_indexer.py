"""Integration tests for AdaptiveSplitMarkdownIndexer against a real Hana DB table.

test_main.py::test_run_indexer_e2e only checks that *some* chunks land in the
table. This module pins down *which* chunks the production indexer stores for a
known set of documents: adaptive header splitting, combined titles, dropping of
chunks below the minimum token count and pass-through of header-less text.
"""

import logging
from unittest.mock import patch

import pytest
from indexing.adaptive_indexer import AdaptiveSplitMarkdownIndexer
from langchain_core.documents import Document

from utils.models import create_embedding_factory, openai_embedding_creator
from utils.settings import DATABASE_USER, EMBEDDING_MODEL_NAME
from utils.utils import sanitize_table_name

# Small thresholds so the sample documents below exercise every branch of the
# adaptive splitter without needing thousand-token fixtures.
MIN_CHUNK_TOKEN_COUNT = 10
MAX_CHUNK_TOKEN_COUNT = 40

DOCUMENTS = [
    # 22 tokens: fits into one chunk, title taken from the H1.
    Document(
        page_content=(
            "# Istio management\nIstio is the service mesh Kyma uses to secure and route traffic between workloads."
        ),
        metadata={"source": "istio.md"},
    ),
    # 63 tokens: exceeds the maximum, so it is split at H1 and then H2 with combined titles.
    Document(
        page_content=(
            "# Serverless\n"
            "The Serverless module lets you run Functions on Kyma without managing Deployments yourself.\n"
            "## Function runtimes\n"
            "Functions can be written in Node.js or Python and are built into container images automatically.\n"
            "## Function triggers\n"
            "A Function is exposed with an APIRule or invoked through an event Subscription."
        ),
        metadata={"source": "serverless.md"},
    ),
    # 6 tokens: below the minimum, merged into adjacent chunk and preserved.
    Document(page_content="# Tiny\nToo short.", metadata={"source": "tiny.md"}),
    # 15 tokens, no header: stored unchanged.
    Document(
        page_content="Plain text without any Markdown headers that still has enough words to be indexed.",
        metadata={"source": "plain.md"},
    ),
]

EXPECTED_CHUNKS = {
    "# Istio management\nIstio is the service mesh Kyma uses to secure and route traffic between workloads.",
    "# Serverless\nThe Serverless module lets you run Functions on Kyma without managing Deployments yourself.",
    "# Serverless - Function runtimes\n"
    "Functions can be written in Node.js or Python and are built into container images automatically.",
    "# Serverless - Function triggers\nA Function is exposed with an APIRule or invoked through an event Subscription.",
    "Plain text without any Markdown headers that still has enough words to be indexed.",
    "# Tiny\nToo short.",
}


@pytest.fixture(scope="module")
def embeddings_model(require_credentials):
    create_embedding = create_embedding_factory(openai_embedding_creator)
    return create_embedding(EMBEDDING_MODEL_NAME)


@pytest.fixture(scope="module")
def table_name(e2e_table_name) -> str:
    # Separate table from test_main.py so both modules can run in any order.
    return sanitize_table_name(f"{e2e_table_name}_adaptive")


@pytest.fixture(scope="module")
def indexer(embeddings_model, hana_conn, table_name):
    indexer = AdaptiveSplitMarkdownIndexer(
        docs_path="",
        embedding=embeddings_model,
        connection=hana_conn,
        table_name=table_name,
        min_chunk_token_count=MIN_CHUNK_TOKEN_COUNT,
        max_chunk_token_count=MAX_CHUNK_TOKEN_COUNT,
    )
    yield indexer
    try:
        cursor = hana_conn.cursor()
        cursor.execute(f'DROP TABLE "{DATABASE_USER}"."{table_name}"')
        cursor.close()
        logging.info(f"Dropped test table '{table_name}'.")
    except Exception:
        logging.exception(f"Failed to drop test table '{table_name}'.")


@pytest.mark.integration
def test_index_stores_adaptively_split_chunks(indexer, hana_conn, table_name):
    with patch("indexing.adaptive_indexer.load_documents", return_value=DOCUMENTS):
        indexer.index()

    cursor = hana_conn.cursor()
    cursor.execute(f'SELECT VEC_TEXT FROM "{DATABASE_USER}"."{table_name}"')
    stored_chunks = {row[0] for row in cursor.fetchall()}
    cursor.close()

    assert stored_chunks == EXPECTED_CHUNKS


@pytest.mark.integration
def test_index_replaces_previous_content(indexer, hana_conn, table_name):
    # A second run must not duplicate chunks: index() swaps in a fresh staging table.
    with patch("indexing.adaptive_indexer.load_documents", return_value=DOCUMENTS):
        indexer.index()
        indexer.index()

    cursor = hana_conn.cursor()
    cursor.execute(f'SELECT COUNT(*) FROM "{DATABASE_USER}"."{table_name}"')
    count = cursor.fetchone()[0]
    cursor.close()

    assert count == len(EXPECTED_CHUNKS)
