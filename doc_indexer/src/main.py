import argparse
import json
import os
import subprocess
import time

from fetcher.fetcher import DocumentsFetcher
from hdbcli import dbapi
from indexing.adaptive_indexer import AdaptiveSplitMarkdownIndexer
from langchain_core.embeddings import Embeddings
from utils.hana import create_hana_connection, drop_table, list_tables

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
    INDEX_TO_FILE,
    PINAKES_BIN,
    PINAKES_CONFIG,
    TMP_DIR,
    get_embedding_model_config,
)

TASK_FETCH = "fetch"
TASK_MATERIALIZE = "materialize"
TASK_INDEX = "index"
TASK_DROP = "drop"
TASK_TABLES = "tables"
logger = get_logger(__name__)


def run_fetcher() -> None:
    """Entry function to run the document fetcher."""
    logger.info("Starting fetch task")
    start = time.monotonic()
    fetcher = DocumentsFetcher(
        source_file=DOCS_SOURCES_FILE_PATH,
        output_dir=DOCS_PATH,
        tmp_dir=TMP_DIR,
    )
    fetcher.run()
    logger.info(f"Fetch completed in {time.monotonic() - start:.1f}s")

    # Log the number of Markdown files per source directory
    md_counts: dict[str, int] = {}
    for root, _dirs, files in os.walk(DOCS_PATH):
        md_count = sum(1 for f in files if f.endswith(".md"))
        if md_count:
            md_counts[root] = md_count
    for dir_path, count in md_counts.items():
        logger.info(f"Found {count} Markdown file(s) in {dir_path}")


def _count_manifest_pages(manifest_path: str) -> int:
    """Return the total number of pages declared across all sources in a pinakes manifest."""
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    return sum(len(source.get("pages", {})) for source in manifest.get("sources", {}).values())


def run_materialize(docs_path: str = DOCS_PATH) -> None:
    """Entry function to materialize the curated corpus with pinakes.

    Reproduces the committed manifest.json into an artifact directory pinakes-style
    (`<source>/<path>.md` plus `<source>/meta.json`) by running
    `pinakes resolve --from-manifest manifest.json --artifact <docs_path>`. This is a drop-in
    alternative to `fetch` that does not need to re-resolve the sources over the network -- it
    reproduces exactly the pages recorded in the manifest.

    Args:
        docs_path: Directory to materialize the artifact into. Defaults to DOCS_PATH from config.
    """
    logger.info("Starting materialize task")
    start = time.monotonic()

    manifest_path = os.path.join(os.path.dirname(PINAKES_CONFIG), "manifest.json")
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(
            f"No pinakes manifest found at {manifest_path}. Commit one with `pinakes resolve` first."
        )

    page_count = _count_manifest_pages(manifest_path)
    logger.info(f"Manifest {manifest_path} declares {page_count} page(s).")

    cmd = [
        PINAKES_BIN,
        "resolve",
        "--from-manifest",
        manifest_path,
        "--config",
        PINAKES_CONFIG,
        "--artifact",
        docs_path,
    ]
    logger.info(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

    logger.info(f"Materialize completed in {time.monotonic() - start:.1f}s")


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
        docs_path: Path to the documents to index. Defaults to DOCS_PATH from config.
        table_name: Name of the table to index into. Defaults to DOCS_TABLE_NAME from config.
    """
    logger.info("Starting index task")
    start = time.monotonic()

    # In INDEX_TO_FILE mode chunks are written to a file and never embedded or written to HANA,
    # so skip creating an embedding model and a DB connection unless the caller injected one --
    # this is what lets the curated-corpus demo run without SAP AI Core or HANA credentials.
    if embeddings_model is None and not INDEX_TO_FILE:
        embedding_model = get_embedding_model_config(EMBEDDING_MODEL_NAME)
        create_embedding = create_embedding_factory(openai_embedding_creator)
        embeddings_model = create_embedding(embedding_model.name)

    if hana_conn is None and not INDEX_TO_FILE:
        hana_conn = create_hana_connection(DATABASE_URL, DATABASE_PORT, DATABASE_USER, DATABASE_PASSWORD)
        if not hana_conn:
            logger.error("Failed to connect to the database. Exiting.")
            raise RuntimeError("Failed to connect to the database.")

    indexer = AdaptiveSplitMarkdownIndexer(docs_path, embeddings_model, hana_conn, table_name)
    indexer.index()
    logger.info(f"Index completed in {time.monotonic() - start:.1f}s")


def run_drop(
    hana_conn: dbapi.Connection | None = None,
    table_name: str = DOCS_TABLE_NAME,
) -> None:
    """Entry function to drop the HANA table created by the indexer.

    Args:
        hana_conn: Hana DB connection to use. If None, created from config.
        table_name: Name of the table to drop. Defaults to DOCS_TABLE_NAME from config.
    """
    logger.info("Starting drop task", extra={"table": table_name})
    if hana_conn is None:
        hana_conn = create_hana_connection(DATABASE_URL, DATABASE_PORT, DATABASE_USER, DATABASE_PASSWORD)
        if not hana_conn:
            logger.error("Failed to connect to the database. Exiting.")
            raise RuntimeError("Failed to connect to the database.")

    drop_table(hana_conn, DATABASE_USER, table_name)


def run_list_tables(
    hana_conn: dbapi.Connection | None = None,
) -> None:
    """Entry function to list all HANA tables owned by the configured user.

    Args:
        hana_conn: Hana DB connection to use. If None, created from config.
    """
    if hana_conn is None:
        hana_conn = create_hana_connection(DATABASE_URL, DATABASE_PORT, DATABASE_USER, DATABASE_PASSWORD)
        if not hana_conn:
            logger.error("Failed to connect to the database. Exiting.")
            raise RuntimeError("Failed to connect to the database.")

    rows = list_tables(hana_conn, DATABASE_USER)
    if not rows:
        logger.info("No tables found.")
        return
    header = f"{'TABLE_NAME':<60} {'ROWS':>10} {'SIZE (bytes)':>14}"
    separator = "-" * 88
    logger.info(f"HANA tables:\n{header}\n{separator}")
    for name, records, size in rows:
        logger.info(f"{name:<60} {records:>10} {size:>14}")
    logger.info(f"{len(rows)} table(s) total.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kyma Documentation Fetcher and Indexer.")
    parser.add_argument("task", choices=["index", "fetch", "materialize", "drop", "tables"])
    args = parser.parse_args()

    logger.info("Indexer job starting", extra={"task": args.task})

    if args.task == TASK_FETCH:
        run_fetcher()
    elif args.task == TASK_MATERIALIZE:
        run_materialize()
    elif args.task == TASK_INDEX:
        run_indexer()
    elif args.task == TASK_DROP:
        run_drop()
    elif args.task == TASK_TABLES:
        run_list_tables()
    else:
        print("Invalid task. Valid tasks are: index, fetch, materialize, drop, tables.")
