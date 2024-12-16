import argparse
import subprocess

from fetcher.fetcher import DocumentsFetcher
from indexing.adaptive_indexer import AdaptiveSplitMarkdownIndexer

from utils.hana import create_hana_connection
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
    EMBEDDING_MODEL_DEPLOYMENT_ID,
    TMP_DIR,
)

TASK_FETCH = "fetch"
TASK_INDEX = "index"


def run_fetcher() -> None:
    """Entry function to run the document fetcher."""
    # create an instance of the fetcher.
    fetcher = DocumentsFetcher(
        source_file=DOCS_SOURCES_FILE_PATH,
        output_dir=DOCS_PATH,
        tmp_dir=TMP_DIR,
    )
    # run the fetcher.
    fetcher.run()
    # print the filtered documents.
    subprocess.run(["tree", DOCS_PATH])


def run_indexer() -> None:
    """Entry function to run the indexer."""
    # init embedding model
    create_embedding = create_embedding_factory(openai_embedding_creator)
    embeddings_model = create_embedding(EMBEDDING_MODEL_DEPLOYMENT_ID)
    # setup connection to Hana Cloud DB
    hana_conn = create_hana_connection(
        DATABASE_URL, DATABASE_PORT, DATABASE_USER, DATABASE_PASSWORD
    )

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
