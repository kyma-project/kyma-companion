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


def create_chunks(
    documents: list[Document], headers_to_split_on: list[tuple[str, str]]
) -> list[Document]:
    """Given the Markdown documents, split them into chunks based on the provided headers."""

    text_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on, strip_headers=False
    )
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
        headers_to_split_on: list[tuple[str, str]] | None = None,
    ):
        if headers_to_split_on is None:
            headers_to_split_on = [HEADER1]
        if not table_name:
            table_name = docs_path.split("/")[-1]

        self.docs_path = docs_path
        self.table_name = table_name
        self.embedding = embedding
        self.headers_to_split_on = headers_to_split_on
        self.db = HanaDB(
            connection=connection,
            embedding=embedding,
            table_name=table_name,
        )

    def _load_documents(self) -> list[Document]:
        # Load all documents from the given directory
        try:
            loader = DirectoryLoader(
                self.docs_path, loader_cls=TextLoader, recursive=True
            )
            docs = loader.load()
            return docs
        except Exception:
            logger.exception("Error while loading documents")
            raise

    def index(self) -> None:
        """
        Indexes the markdown files in the given directory.
        It uses ('#', 'Header1') as the default header to split on.
        """

        docs = self._load_documents()

        # chunk the documents by the headers
        all_chunks = create_chunks(docs, self.headers_to_split_on)

        logger.info(
            f"Indexing {len(all_chunks)} markdown files chunks for {self.table_name}..."
        )

        logger.info("Deleting existing index in HanaDB...")
        try:
            self.db.delete(filter={})
        except Exception:
            logger.exception("Error while deleting existing documents in HanaDB.")
            raise
        logger.info("Successfully deleted existing documents in HanaDB.")

        logger.info("Indexing and storing indexes to HanaDB...")
        for i in range(0, len(all_chunks), CHUNKS_BATCH_SIZE):
            batch = all_chunks[i : i + CHUNKS_BATCH_SIZE]
            try:
                # Add current batch of documents
                self.db.add_documents(batch)
                logger.info(
                    f"Indexed batch {i//CHUNKS_BATCH_SIZE + 1} of {len(all_chunks)//CHUNKS_BATCH_SIZE + 1}"
                )

                # Wait 3 seconds before processing next batch
                # if i + CHUNKS_BATCH_SIZE < len(all_chunks):
                #     time.sleep(1)

            except Exception:
                logger.exception(
                    f"Error while storing documents batch {i//CHUNKS_BATCH_SIZE + 1} in HanaDB"
                )
                raise

        logger.info(f"Successfully indexed {len(all_chunks)} markdown files chunks.")
