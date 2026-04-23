import argparse
import subprocess

from fetcher.fetcher import DocumentsFetcher
from hdbcli import dbapi
from indexing.adaptive_indexer import AdaptiveSplitMarkdownIndexer
from langchain_core.embeddings import Embeddings
from utils.hana import create_hana_connection

from utils.logging import get_logger
from utils.models import (
    create_embedding_factory,
    fastembed_embedding_creator,
    openai_embedding_creator,
)
from utils.settings import (
    DATABASE_PASSWORD,
    DATABASE_PORT,
    DATABASE_URL,
    DATABASE_USER,
    DOCS_PATH,
    DOCS_SOURCES_FILE_PATH,
    DOCS_TABLE_NAME,
    EMBEDDING_MODEL_NAME,
    INDEX_OUTPUT_DIR,
    INDEX_TO_FILE,
    KYMA_VERSION,
    LOCAL_EMBED_MODEL,
    TMP_DIR,
    get_embedding_model_config,
)

TASK_FETCH = "fetch"
TASK_INDEX = "index"

logger = get_logger(__name__)


def run_fetcher() -> None:
    """Entry function to run the document fetcher."""
    # create an instance of the fetcher.
    fetcher = DocumentsFetcher(
        source_file=DOCS_SOURCES_FILE_PATH,
        output_dir=DOCS_PATH,
        tmp_dir=TMP_DIR,
    )
    # run the fetcher
    fetcher.run()
    # print the filtered documents
    try:
        subprocess.run(["tree", DOCS_PATH])
    except Exception:
        logger.warning("Fetcher Completed but Failed to print the documents list")


def run_indexer(
    embeddings_model: Embeddings | None = None,
    hana_conn: dbapi.Connection | None = None,
    docs_path: str = DOCS_PATH,
    table_name: str = DOCS_TABLE_NAME,
) -> None:
    """Entry function to run the indexer.

    Args:
        embeddings_model: Embedding model to use. If None, created from config.
        hana_conn: Hana DB connection to use. If None, created from config.
            Ignored when INDEX_TO_FILE=true.
        docs_path: Path to the documents to index.
            Defaults to DOCS_PATH from config.
        table_name: Name of the table to index into.
            Defaults to DOCS_TABLE_NAME from config.
    """
    if INDEX_TO_FILE:
        _run_local_file_indexer(docs_path, table_name)
        return

    if embeddings_model is None:
        embedding_model = get_embedding_model_config(EMBEDDING_MODEL_NAME)
        create_embedding = create_embedding_factory(openai_embedding_creator)
        embeddings_model = create_embedding(embedding_model.name)

    if hana_conn is None:
        hana_conn = create_hana_connection(DATABASE_URL, DATABASE_PORT, DATABASE_USER, DATABASE_PASSWORD)
        if not hana_conn:
            logger.error("Failed to connect to the database. Exiting.")
            raise RuntimeError("Failed to connect to the database.")

    indexer = AdaptiveSplitMarkdownIndexer(docs_path, embeddings_model, hana_conn, table_name)
    indexer.index()


def _run_local_file_indexer(docs_path: str, collection_name: str) -> None:
    """Build a ChromaDB index from docs and package it as a .tar.gz archive."""
    from indexing.local_file_indexer import LocalFileIndexer

    logger.info(
        f"INDEX_TO_FILE=true — building local ChromaDB index (model={LOCAL_EMBED_MODEL}, output={INDEX_OUTPUT_DIR})"
    )
    embedding = fastembed_embedding_creator(LOCAL_EMBED_MODEL)
    indexer = LocalFileIndexer(
        docs_path=docs_path,
        embedding=embedding,
        output_dir=INDEX_OUTPUT_DIR,
        embed_model_name=LOCAL_EMBED_MODEL,
        collection_name=collection_name,
    )
    indexer.index()

    archive_name = f"kyma-docs-index-{KYMA_VERSION}.tar.gz"
    LocalFileIndexer.package(INDEX_OUTPUT_DIR, archive_name)
    logger.info(f"Local index ready: {archive_name}")


if __name__ == "__main__":
    # read command line argument.
    parser = argparse.ArgumentParser(description="Kyma Documentation Fetcher and Indexer.")
    parser.add_argument("task", choices=["index", "fetch"])
    args = parser.parse_args()

    # run the specified task.
    if args.task == TASK_FETCH:
        run_fetcher()
    elif args.task == TASK_INDEX:
        run_indexer()
    else:
        print("Invalid task. Valid tasks are: index, fetch.")
