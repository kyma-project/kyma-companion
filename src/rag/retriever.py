"""HANA DB retriever for the RAG system.

The table is the one of the current index run of a corpus, resolved per request
through ``CurrentRunTable`` (ported from kyma-agent).
"""

import threading
import time

from hdbcli import dbapi
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.runnables import run_in_executor
from langchain_hana import HanaDB

from rag.current_run import CurrentRunTable, CurrentRunTableMissingError, RunTableError
from services.metrics import CustomMetrics
from utils.logging import get_logger

logger = get_logger(__name__)

# HANA SQL error "invalid table name" (the table does not exist).
_HANA_INVALID_TABLE_NAME = 259


class TableNotFoundError(RuntimeError):
    """Raised when the table of a run does not exist."""


class HanaVectorDB(HanaDB):
    """HANA DB Vector Store (read only)."""

    def __init__(
        self,
        connection: dbapi.Connection,
        embedding: Embeddings,
        table_name: str,
    ):
        super().__init__(connection, embedding, table_name=table_name)

    def _initialize_table(self) -> None:
        # HanaDB creates a missing table; a reader must not, the run may have been dropped.
        if not self._table_exists(self.table_name):
            raise TableNotFoundError(f"table {self.table_name} does not exist")
        super()._initialize_table()


def _is_missing_table(error: Exception) -> bool:
    if isinstance(error, TableNotFoundError):
        return True
    return isinstance(error, dbapi.Error) and error.errorcode == _HANA_INVALID_TABLE_NAME


class HanaDBRetriever:
    """HANA DB Retriever over the table of the current run of a corpus."""

    def __init__(
        self,
        embedding: Embeddings,
        connection: dbapi.Connection,
        current_run: CurrentRunTable,
    ):
        self.embedding = embedding
        self.connection = connection
        self.current_run = current_run
        self._db: HanaVectorDB | None = None
        self._db_lock = threading.Lock()

    def _get_db(self, table: str) -> HanaVectorDB:
        """Return the vector store of ``table``; rebuilt only when the table changes."""
        with self._db_lock:
            if self._db is None or self._db.table_name != table:
                self._db = HanaVectorDB(
                    connection=self.connection,
                    embedding=self.embedding,
                    table_name=table,
                )
            return self._db

    def _search(self, query: str, k: int) -> list[Document]:
        """Blocking search; on a missing table resolve the current run again and retry once.

        Raises CurrentRunTableMissingError when the table is still missing after the retry:
        the run table points at a table that does not exist.
        """
        table = self.current_run.resolve()
        try:
            return self._get_db(table).similarity_search(query, k=k)
        except (dbapi.Error, TableNotFoundError) as e:
            if not _is_missing_table(e):
                raise
            # Parallel searches fail on the same table; only the one that clears the cache warns.
            if self.current_run.invalidate(table):
                logger.warning(
                    f"Table {table} of the current run of corpus {self.current_run.corpus} is "
                    "gone; resolving the current run again."
                )
            else:
                logger.debug(f"Table {table} is gone, retrying with the current run.")
        table = self.current_run.resolve()
        try:
            return self._get_db(table).similarity_search(query, k=k)
        except (dbapi.Error, TableNotFoundError) as e:
            if not _is_missing_table(e):
                raise
            raise CurrentRunTableMissingError(
                f"the run table {self.current_run.runs_table} of corpus {self.current_run.corpus} "
                f"points at table {table}, which does not exist"
            ) from e

    async def aretrieve(self, query: str, top_k: int = 5) -> list[Document]:
        """Retrieve relevant documents based on the query."""
        start_time = time.perf_counter()
        try:
            docs = await run_in_executor(None, self._search, query, top_k)
        except RunTableError:
            # A state of the run table, not a bug: no traceback, no exception text.
            logger.error(
                f"No usable current run of corpus {self.current_run.corpus} in run table "
                f"{self.current_run.runs_table}; cannot retrieve documents."
            )
            await CustomMetrics().record_hanadb_latency(time.perf_counter() - start_time, False)
            raise
        except Exception:
            logger.exception(f"Error retrieving documents for query: {query}")
            await CustomMetrics().record_hanadb_latency(time.perf_counter() - start_time, False)
            raise
        await CustomMetrics().record_hanadb_latency(time.perf_counter() - start_time, True)
        return docs
