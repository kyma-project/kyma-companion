import time
from typing import Protocol

from hdbcli import dbapi
from indexing.constants import HEADER1
from langchain_community.document_loaders import DirectoryLoader
from langchain_community.document_loaders.text import TextLoader
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_hana import HanaDB
from langchain_text_splitters import MarkdownHeaderTextSplitter

from utils.logging import get_logger
from utils.settings import CHUNKS_BATCH_SIZE, DATABASE_USER

logger = get_logger(__name__)

ERR_SQL_INV_TABLE = 259  # SQL error code for invalid table name in HANA Databases.


def create_chunks(documents: list[Document], headers_to_split_on: list[tuple[str, str]]) -> list[Document]:
    """Given the Markdown documents, split them into chunks based on the provided headers."""

    text_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on, strip_headers=False)
    all_chunks: list[Document] = []
    try:
        for doc in documents:
            chunks = text_splitter.split_text(doc.page_content)
            all_chunks.extend([chunk for chunk in chunks if chunk.page_content.strip()])
        logger.info(f"Successfully created {len(all_chunks)} document chunks.")
    except Exception:
        logger.exception("Error while creating document chunks")
        raise

    return all_chunks


class IIndexer(Protocol):
    """Indexer interface."""

    def index(self) -> None:
        """Index the markdown files in the given directory."""
        ...


class MarkdownIndexer:
    """Markdown indexer implements indexing markdown files into HanaDB."""

    def __init__(
        self,
        docs_path: str,
        embedding: Embeddings,
        connection: dbapi.Connection,
        table_name: str | None = None,
        backup_table_name: str | None = None,
        headers_to_split_on: list[tuple[str, str]] | None = None,
    ):
        if headers_to_split_on is None:
            headers_to_split_on = [HEADER1]
        if not table_name:
            table_name = docs_path.split("/")[-1]

        self.docs_path = docs_path
        self.embedding = embedding
        self.headers_to_split_on = headers_to_split_on
        self.db = HanaDB(
            connection=connection,
            embedding=embedding,
            table_name=table_name,
        )
        self.backup_table_name = backup_table_name or f"{self.db.table_name}_backup_{int(time.time())}"

    def _load_documents(self) -> list[Document]:
        # Load all documents from the given directory
        try:
            loader = DirectoryLoader(self.docs_path, loader_cls=TextLoader, recursive=True)
            docs = loader.load()
            return docs
        except Exception:
            logger.exception("Error while loading documents")
            raise

    def _handle_database_operation(self, operation: str, only_warn_if_table_inexistent: bool = True) -> None:
        """
        Executes a database operation using the provided SQL statement.

        Handles exceptions related to missing tables and other database errors.
        If the table does not exist and only_warn_if_table_inexistent is True,
        logs a warning; otherwise, logs the exception and raises it.

        Args:
            operation (str): The SQL statement to execute.
            only_warn_if_table_inexistent (bool): If True, only warns when the table does not exist;
                if False, raises the exception.

        Raises:
            dbapi.ProgrammingError: If a programming error occurs and only_warn_if_table_inexistent is False.
            Exception: For any other database-related errors.
        """
        try:
            with self.db.connection.cursor() as cursor:
                cursor.execute(operation)
                self.db.connection.commit()
        except dbapi.ProgrammingError as e:
            if e.args and e.args[0] == ERR_SQL_INV_TABLE and only_warn_if_table_inexistent:
                logger.warning(f"While operating with '{operation}', table does not exist in HanaDB.")
                return
            logger.exception(f"Error while operating with '{operation}' in HanaDB.")
            raise
        except Exception:
            logger.exception(f"Error while operating with '{operation}' in HanaDB.")
            raise

    def _copy_table(
        self,
        source_table: str,
        target_table: str,
        only_warn_if_table_inexistent: bool = True,
    ) -> None:
        """
        copies a table in hanadb from source_table to target_table, including structure and data.

        drops the target table if it exists to avoid duplicate table errors, then creates
        the target table as a copy of the source table.

        args:
            source_table (str): name of the table to copy from.
            target_table (str): name of the table to copy to.
            only_warn_if_table_inexistent (bool): if true, only warns if the table does not exist;
                if false, raises an exception.

        raises:
            dbapi.programmingerror: if a programming error occurs and only_warn_if_table_inexistent is false.
            exception: for any other database-related errors.
        """
        logger.info(f"Copying table {source_table} to {target_table}...")
        # Drop the target table if it exists to avoid duplicate table errors
        self._drop_table(target_table, only_warn_if_table_inexistent=True)
        op = f'CREATE TABLE "{DATABASE_USER}"."{target_table}" AS (SELECT * FROM "{DATABASE_USER}"."{source_table}")'
        self._handle_database_operation(op, only_warn_if_table_inexistent)

    def _drop_table(self, table_name: str, only_warn_if_table_inexistent: bool = True) -> None:
        """
        Drops the specified table from the HanaDB schema.

        Args:
            table_name (str): Name of the table to drop.
            only_warn_if_table_inexistent (bool, optional): If True, only logs a warning if the table does not exist.
        """
        logger.info(f"Dropping table {table_name} if exists...")
        operation = f'DROP TABLE "{DATABASE_USER}"."{table_name}"'
        self._handle_database_operation(operation, only_warn_if_table_inexistent)

    def _rename_table(self, old_name: str, new_name: str, only_warn_if_table_inexistent: bool = True) -> None:
        """
        Renames a table in the HanaDB schema.

        Args:
            old_name (str): Current name of the table.
            new_name (str): New name for the table.
            only_warn_if_table_inexistent (bool, optional): If True,
                only logs a warning if the source table does not exist.
        """
        logger.info(f"Renaming table {old_name} to {new_name}...")
        operation = f'RENAME TABLE "{DATABASE_USER}"."{old_name}" TO "{DATABASE_USER}"."{new_name}"'
        self._handle_database_operation(operation, only_warn_if_table_inexistent=only_warn_if_table_inexistent)

    def _index_chunks_in_batches(self, chunks: list[Document]) -> None:
        """
        Indexes and stores document chunks in batches to the temporary HanaDB table.

        Args:
            chunks (list[Document]): List of document chunks to index and store.
        """
        logger.info("Indexing and storing indexes to HanaDB...")
        for i in range(0, len(chunks), CHUNKS_BATCH_SIZE):
            batch = chunks[i : i + CHUNKS_BATCH_SIZE]
            try:
                self.db.add_documents(batch)
                logger.info(f"Indexed batch {i // CHUNKS_BATCH_SIZE + 1} of {len(chunks) // CHUNKS_BATCH_SIZE + 1}")
                if i + CHUNKS_BATCH_SIZE < len(chunks):
                    time.sleep(3)
            except:
                logger.exception(f"Batch {i // CHUNKS_BATCH_SIZE + 1} failed")
                raise
        logger.info(f"Successfully indexed {len(chunks)} markdown files chunks to {self.db.table_name} table.")

    def index(self) -> None:
        """
        Indexes markdown files in the specified directory by chunking them and storing the chunks in the database.

        The process involves:
            1. Loading and chunking markdown documents by specified headers.
            2. Backing up the current main table (if it exists).
            3. Deleting all data from the main table.
            4. Storing new document chunks in the main table.
            5. On error, restoring the main table from backup.

        Raises:
            Exception: If indexing fails and restoration from backup is attempted.
        """

        docs = self._load_documents()

        # Chunk the documents by the headers.
        chunks = create_chunks(docs, self.headers_to_split_on)

        # Create a backup of the current main table (if exists).
        logger.info(f"Backing up current table {self.db.table_name} to {self.backup_table_name} if exists...")
        self._copy_table(
            self.db.table_name,
            self.backup_table_name,
            only_warn_if_table_inexistent=True,
        )

        try:
            # Drop any old temporary table.
            logger.info(f"Cleaning data from {self.db.table_name}.")
            self.db.delete(filter={})

            # Store all new document chunks in the temporary table.
            logger.info(f"Indexing {len(chunks)} markdown files chunks for {self.db.table_name}...")
            self._index_chunks_in_batches(chunks)
        except Exception:
            logger.exception("Error during indexing. Attempting to restore from backup.")
            self._drop_table(self.db.table_name, only_warn_if_table_inexistent=True)
            self._rename_table(
                self.backup_table_name,
                self.db.table_name,
                only_warn_if_table_inexistent=True,
            )
            raise
        # Clean up the backup table after successful indexing.
        self._drop_table(self.backup_table_name, only_warn_if_table_inexistent=True)
