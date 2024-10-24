import logging
from typing import List, Protocol

from hdbcli import dbapi
from langchain_community.document_loaders import DirectoryLoader
from langchain_community.document_loaders.text import TextLoader
from langchain_community.vectorstores import HanaDB
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter

from indexing.contants import HEADER1


def create_chunks(documents: List[Document], headers_to_split_on) -> List[Document]:
    """Given the Markdown documents, split them into chunks based on the provided headers."""

    text_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on, strip_headers=False
    )
    all_chunks: List[Document] = []
    try:
        for doc in documents:
            chunks = text_splitter.split_text(doc.page_content)
            all_chunks.extend([chunk for chunk in chunks if chunk.page_content.strip()])
        logging.info(f"Successfully created {len(all_chunks)} document chunks.")
    except Exception as e:
        logging.error(f"Error while creating document chunks: {e}")
        raise

    return all_chunks


class IIndexer(Protocol):
    def index(self, docs_path: str) -> None: ...


class MarkdownIndexer:
    db = None
    connection = None

    def __init__(
        self,
        docs_path: str,
        embedding: Embeddings,
        connection: dbapi.Connection,
        table_name=None,
    ):
        if not table_name:
            table_name = docs_path.split("/")[-1]

        self.docs_path = docs_path
        self.table_name = table_name
        self.embedding = embedding

        self.db = HanaDB(
            connection=connection,
            embedding=embedding,
            table_name=table_name,
        )

    def _load_documents(self) -> List[Document]:
        # Load all documents from the given directory
        try:
            loader = DirectoryLoader(
                self.docs_path, loader_cls=TextLoader, recursive=True
            )
            docs = loader.load()
            return docs
        except Exception:
            logging.exception(f"Error while loading documents")
            raise

    def index(self, headers_to_split_on=None):
        """
        Indexes the markdown files in the given directory.
        It uses ('#', 'Header1') as the default header to split on.
        """

        if not headers_to_split_on:
            headers_to_split_on = [HEADER1]

        docs = self._load_documents()

        # chunk the documents by the headers
        all_chunks = create_chunks(docs, headers_to_split_on)

        logging.info(
            f"Indexing {len(all_chunks)} markdown files chunks for {self.table_name}..."
        )

        # TODO: check if overwrite works without deleting the data
        # overwrite the existing data
        try:
            self.db.delete(filter={})
        except Exception:
            logging.error(f"Error while deleting existing documents in HanaDB.")
            raise

        try:
            self.db.add_documents(all_chunks)
        except Exception:
            logging.error(f"Error while storing documents chunks in HanaDB.")
            raise
