import argparse
import subprocess

from fetcher.fetcher import DocumentsFetcher
from indexing.adaptive_indexer import AdaptiveSplitMarkdownIndexer
from utils.hana import create_hana_connection

from utils.logging import get_logger
from utils.models import (
    create_embedding_factory,
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


def run_indexer() -> None:
    """Entry function to run the indexer."""
    # init embedding model
    embedding_model = get_embedding_model_config(EMBEDDING_MODEL_NAME)
    create_embedding = create_embedding_factory(openai_embedding_creator)
    embeddings_model = create_embedding(embedding_model.deployment_id)
    # setup connection to Hana Cloud DB
    hana_conn = create_hana_connection(
        DATABASE_URL, DATABASE_PORT, DATABASE_USER, DATABASE_PASSWORD
    )
    if not hana_conn:
        logger.error("Failed to connect to the database. Exiting.")
        raise

    indexer = AdaptiveSplitMarkdownIndexer(
        DOCS_PATH, embeddings_model, hana_conn, DOCS_TABLE_NAME
    )
    indexer.index()


if __name__ == "__main__":
    # read command line argument.
    parser = argparse.ArgumentParser(
        description="Kyma Documentation Fetcher and Indexer."
    )
    parser.add_argument("task", choices=["index", "fetch"])
    args = parser.parse_args()

    # run the specified task.
    if args.task == TASK_FETCH:
        run_fetcher()
    elif args.task == TASK_INDEX:
        run_indexer()
    else:
        print("Invalid task. Valid tasks are: index, fetch.")
