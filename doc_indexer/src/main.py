import argparse
import json
import subprocess
import sys
import time

from fetcher.fetcher import DocumentsFetcher
from hdbcli import dbapi
from indexing.adaptive_indexer import AdaptiveSplitMarkdownIndexer
from langchain_core.embeddings import Embeddings
from utils.hana import VerifyStats, create_hana_connection, drop_table, list_tables, verify_table

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
TASK_DROP = "drop"
TASK_TABLES = "tables"
TASK_VERIFY = "verify"
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
        docs_path: Path to the documents to index. Defaults to DOCS_PATH from config.
        table_name: Name of the table to index into. Defaults to DOCS_TABLE_NAME from config.
    """
    logger.info("Starting index task")
    start = time.monotonic()

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


def run_verify(
    hana_conn: dbapi.Connection | None = None,
    table_name: str = DOCS_TABLE_NAME,
    sources_file: str = DOCS_SOURCES_FILE_PATH,
) -> None:
    """Entry function to verify the indexed documentation table.

    Queries the HANA table and prints a health report. Exits with code 1
    when the table is empty, any configured module has zero rows, or rows
    with missing metadata are found.

    Args:
        hana_conn: Hana DB connection to use. If None, created from config.
        table_name: Name of the table to verify. Defaults to DOCS_TABLE_NAME from config.
        sources_file: Path to the docs-sources JSON file used to read configured module names.
    """
    if hana_conn is None:
        hana_conn = create_hana_connection(DATABASE_URL, DATABASE_PORT, DATABASE_USER, DATABASE_PASSWORD)
        if not hana_conn:
            logger.error("Failed to connect to the database. Exiting.")
            raise RuntimeError("Failed to connect to the database.")

    # Load configured module names from the sources file
    configured_modules: list[str] = []
    try:
        with open(sources_file, encoding="utf-8") as f:
            sources = json.load(f)
        configured_modules = [entry["name"] for entry in sources if "name" in entry]
    except FileNotFoundError:
        logger.warning(f"Sources file not found: {sources_file}. Module zero-row check will be skipped.")
    except Exception:
        logger.exception(f"Failed to read sources file {sources_file}. Module zero-row check will be skipped.")

    stats: VerifyStats = verify_table(hana_conn, DATABASE_USER, table_name, configured_modules)

    _print_verify_report(stats, table_name)

    # Determine exit code: 1 if any hard failure, 0 otherwise
    has_error = stats.total_rows == 0 or bool(stats.zero_row_modules) or stats.missing_metadata_rows > 0
    if has_error:
        sys.exit(1)


def _print_verify_report(stats: VerifyStats, table_name: str) -> None:
    """Print the verification report to the logger.

    Args:
        stats: The collected :class:`~utils.hana.VerifyStats`.
        table_name: Table name included in the report header.
    """
    col_w = 40
    val_w = 10
    header = f"{'METRIC':<{col_w}} {'VALUE':>{val_w}}"
    separator = "-" * (col_w + val_w + 1)

    lines = [f"Verify report for table: {table_name}", header, separator]

    def _row(label: str, value: int | str) -> str:
        return f"{label:<{col_w}} {str(value):>{val_w}}"

    lines.append(_row("Total rows", stats.total_rows))
    for module, count in sorted(stats.rows_per_module.items()):
        lines.append(_row(f"  rows [{module}]", count))
    if stats.zero_row_modules:
        lines.append(_row("Modules with zero rows (ERROR)", ", ".join(sorted(stats.zero_row_modules))))
    lines.append(_row("Duplicate chunks (warning)", stats.duplicate_chunks))
    lines.append(_row("Oversized chunks >6000 chars (warning)", stats.oversized_chunks))
    lines.append(_row("Rows missing title/url (ERROR)", stats.missing_metadata_rows))

    logger.info("\n".join(lines))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kyma Documentation Fetcher and Indexer.")
    parser.add_argument("task", choices=["index", "fetch", "drop", "tables", "verify"])
    args = parser.parse_args()

    logger.info("Indexer job starting", extra={"task": args.task})

    if args.task == TASK_FETCH:
        run_fetcher()
    elif args.task == TASK_INDEX:
        run_indexer()
    elif args.task == TASK_DROP:
        run_drop()
    elif args.task == TASK_TABLES:
        run_list_tables()
    elif args.task == TASK_VERIFY:
        run_verify()
    else:
        print("Invalid task. Valid tasks are: index, fetch, drop, tables, verify.")
