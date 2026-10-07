import argparse
import os
import time

from fetcher.fetcher import DocumentsFetcher
from hdbcli import dbapi
from indexing.adaptive_indexer import AdaptiveSplitMarkdownIndexer
from langchain_core.embeddings import Embeddings
from langchain_hana import HanaDB
from transfer import export_hana, export_pgvector, run_import_file
from utils.hana import create_hana_connection, drop_table, list_tables
from writers.base import Writer
from writers.file import FileWriter
from writers.hana import HanaWriter
from writers.pgvector import PgVectorWriter
from writers.tee import TeeWriter

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
    DOCS_FILE_PATH,
    DOCS_PATH,
    DOCS_SEARCH_PG_DSN,
    DOCS_SOURCES_FILE_PATH,
    DOCS_TABLE_NAME,
    DOCS_WRITER,
    EMBEDDING_MODEL_NAME,
    INDEX_TO_FILE,
    TMP_DIR,
    get_embedding_model_config,
)

TASK_FETCH = "fetch"
TASK_INDEX = "index"
TASK_DROP = "drop"
TASK_TABLES = "tables"
TASK_IMPORT = "import"
TASK_EXPORT = "export"
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
    for root, _dirs, files in os.walk(DOCS_PATH):
        level = root.replace(DOCS_PATH, "").count(os.sep)
        indent = "  " * level
        logger.info(f"{indent}{os.path.basename(root)}/")
        for fname in files:
            logger.info(f"{indent}  {fname}")


class _NoEmbeddings(Embeddings):
    """Placeholder for HanaDB when vectors are always passed in (import task)."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        raise RuntimeError("embedding is not available here")

    def embed_query(self, text: str) -> list[float]:
        raise RuntimeError("embedding is not available here")


def _hana_connection(hana_conn: dbapi.Connection | None) -> dbapi.Connection:
    if hana_conn is None:
        hana_conn = create_hana_connection(DATABASE_URL, DATABASE_PORT, DATABASE_USER, DATABASE_PASSWORD)
        if not hana_conn:
            logger.error("Failed to connect to the database. Exiting.")
            raise RuntimeError("Failed to connect to the database.")
    return hana_conn


def build_writer(
    embeddings_model: Embeddings,
    hana_conn: dbapi.Connection | None,
    table_name: str,
    force_explicit_hana: bool = False,
) -> Writer | None:
    """Build the writer(s) from DOCS_WRITER (comma-separated). Returns None for plain "hana" (indexer default)."""
    names = [n.strip() for n in DOCS_WRITER.split(",") if n.strip()]
    if INDEX_TO_FILE and names == ["hana"]:
        names = ["file"]
    if names == ["hana"] and not force_explicit_hana:
        # keep the existing path: the indexer builds its own HanaWriter from the connection
        return None
    writers: list[Writer] = []
    for name in names:
        if name == "pgvector":
            if not DOCS_SEARCH_PG_DSN:
                raise RuntimeError("DOCS_SEARCH_PG_DSN must be set for DOCS_WRITER=pgvector.")
            writers.append(PgVectorWriter(DOCS_SEARCH_PG_DSN))
        elif name == "file":
            writers.append(FileWriter(DOCS_FILE_PATH))
        elif name == "hana":
            db = HanaDB(connection=_hana_connection(hana_conn), embedding=embeddings_model, table_name=table_name)
            writers.append(HanaWriter(db))
        else:
            raise ValueError(f"Unknown DOCS_WRITER: {name}")
    return writers[0] if len(writers) == 1 else TeeWriter(writers)


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

    writer = build_writer(embeddings_model, hana_conn, table_name)
    if writer is None:
        hana_conn = _hana_connection(hana_conn)

    indexer = AdaptiveSplitMarkdownIndexer(
        docs_path,
        embeddings_model,
        hana_conn,
        table_name,
        writer=writer,
        embedding_model_name=EMBEDDING_MODEL_NAME,
    )
    indexer.index()
    logger.info(f"Index completed in {time.monotonic() - start:.1f}s")


def run_import(path: str, table_name: str = DOCS_TABLE_NAME) -> None:
    """Import a file-writer JSON through the configured writer(s) with a new run id; vectors are not recomputed."""
    logger.info("Starting import task", extra={"file": path})
    writer = build_writer(_NoEmbeddings(), None, table_name, force_explicit_hana=True)
    assert writer is not None
    run_import_file(path, writer)


def run_export(source: str, path: str, table_name: str = DOCS_TABLE_NAME) -> None:
    """Write the current index of the source store (hana | pgvector) to a file-writer JSON."""
    logger.info("Starting export task", extra={"source": source, "file": path})
    if source == "pgvector":
        if not DOCS_SEARCH_PG_DSN:
            raise RuntimeError("DOCS_SEARCH_PG_DSN must be set for --from pgvector.")
        export_pgvector(DOCS_SEARCH_PG_DSN, path)
    elif source == "hana":
        export_hana(_hana_connection(None), DATABASE_USER, table_name, EMBEDDING_MODEL_NAME, path)
    else:
        raise ValueError(f"Unknown export source: {source}")


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
    parser.add_argument("task", choices=["index", "fetch", "drop", "tables", "import", "export"])
    parser.add_argument("--file", help="import: file to read; export: file to write")
    parser.add_argument("--from", dest="source", choices=["hana", "pgvector"], help="export: source store")
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
    elif args.task == TASK_IMPORT:
        if not args.file:
            parser.error("import requires --file")
        run_import(args.file)
    elif args.task == TASK_EXPORT:
        if not args.file or not args.source:
            parser.error("export requires --from and --file")
        run_export(args.source, args.file)
    else:
        print("Invalid task. Valid tasks are: index, fetch, drop, tables.")
