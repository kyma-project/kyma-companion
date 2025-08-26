import time
from typing import Protocol

from hdbcli import dbapi
from indexing.contants import HEADER1
from langchain_community.document_loaders import DirectoryLoader
from langchain_community.document_loaders.text import TextLoader
from langchain_community.vectorstores import HanaDB
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter

from utils.logging import get_logger
from utils.settings import CHUNKS_BATCH_SIZE

logger = get_logger(__name__)


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

    def index(self, docs_path: str) -> None:
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
        temp_table_name: str = "temp_table",
        backup_table_name: str = "backup_table",
        headers_to_split_on: list[tuple[str, str]] | None = None,
    ):
        if headers_to_split_on is None:
            headers_to_split_on = [HEADER1]
        if not table_name:
            table_name = docs_path.split("/")[-1]

        self.docs_path = docs_path
        self.main_table_name = table_name
        self.backup_table_name = backup_table_name
        self.embedding = embedding
        self.headers_to_split_on = headers_to_split_on
        self.db = HanaDB(
            connection=connection,
            embedding=embedding,
            table_name=temp_table_name,
        )

    @property
    def temp_table_name(self) -> str:
        """
        Returns the name of the temporary table used in the database.
        """
        return self.db.table_name

    def _load_documents(self) -> list[Document]:
        # Load all documents from the given directory
        try:
            loader = DirectoryLoader(self.docs_path, loader_cls=TextLoader, recursive=True)
            docs = loader.load()
            return docs
        except Exception:
            logger.exception("Error while loading documents")
            raise

    def _drop_table(self, table_name: str) -> None:
        """Drop the given table from the HanaDB."""
        cursor = self.db.connection.cursor()
        try:
            logger.info(f"Dropping table {table_name} if exists...")
            cursor.execute(f"DROP TABLE {table_name}")
            self.db.connection.commit()
        except Exception:
            logger.exception(f"Error while dropping table {table_name} in HanaDB.")
        finally:
            cursor.close()

    def _rename_table(self, old_name: str, new_name: str) -> None:
        """Rename the given table in the HanaDB."""
        cursor = self.db.connection.cursor()
        try:
            logger.info(f"Renaming table {old_name} to {new_name}...")
            cursor.execute(f"RENAME TABLE {old_name} TO {new_name}")
            self.db.connection.commit()
        except Exception:
            logger.exception(f"Error while renaming table {old_name} to {new_name} in HanaDB.")
        finally:
            cursor.close()

    def _index_chunks_in_batches(self, chunks: list[Document]) -> None:
        """Store all new document chunks in the temporary table."""
        logger.info("Indexing and storing indexes to HanaDB...")
        for i in range(0, len(chunks), CHUNKS_BATCH_SIZE):
            batch = chunks[i : i + CHUNKS_BATCH_SIZE]
            try:
                self.db.add_documents(batch)
                logger.info(f"Indexed batch {i // CHUNKS_BATCH_SIZE + 1} of {len(chunks) // CHUNKS_BATCH_SIZE + 1}")
                if i + CHUNKS_BATCH_SIZE < len(chunks):
                    time.sleep(3)
            except Exception as e:
                logger.error(f"Batch {i // CHUNKS_BATCH_SIZE + 1} failed: {e}")
                raise
        logger.info(f"Successfully indexed {len(chunks)} markdown files chunks to {self.temp_table_name} table.")

    def index(self) -> None:
        """
        Indexes the markdown files in the given directory
        by chunking and storing them in the database.
        The symbol '#' ('Header1') is used as the default header to split.

        Database table operations performed in order:
        1. Drops the temporary table (if exists) to ensure a clean state.
        2. Stores all new document chunks in the temporary table.
        3. Drops the backup table (if exists).
        4. Renames the current main table to the backup table.
        5. Renames the temporary table to become the new main table.
        6. If renaming the temporary table fails, restores the backup table as the main table.
        """

        docs = self._load_documents()

        # Chunk the documents by the headers.
        chunks = create_chunks(docs, self.headers_to_split_on)

        # Drop the temporary table (if exists) to ensure a clean state.
        self._drop_table(self.temp_table_name)

        # Store all new document chunks in the temporary table.
        logger.info(f"Indexing {len(chunks)} markdown files chunks for {self.temp_table_name}...")
        self._index_chunks_in_batches(chunks)

        # Drop the backup table (if exists).
        self._drop_table(self.backup_table_name)

        # Rename the current main table to the backup table.
        self._rename_table(self.main_table_name, self.backup_table_name)

        # Rename the temporary table to become the new main table.
        try:
            self._rename_table(self.temp_table_name, self.main_table_name)
        except Exception:
            # If renaming the temporary table fails, restore the backup table as the main table.
            logger.exception(
                f"Error while renaming temporary table {self.temp_table_name} to {self.main_table_name} in HanaDB."
            )
            logger.info(f"Restoring backup table {self.backup_table_name} to {self.main_table_name}.")
            self._rename_table(self.backup_table_name, self.main_table_name)
            raise
