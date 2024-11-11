from typing import Protocol

from hdbcli import dbapi
from langchain_community.vectorstores import HanaDB
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings


class IRetriever(Protocol):
    """Retriever interface."""

    def retrieve(self, query: str) -> list[Document]:
        """Retrieve relevant documents based on the query."""
        ...


class HanaDBRetriever:
    """Retriever for HanaDB."""

    def __init__(
        self, embedding: Embeddings, connection: dbapi.Connection, table_name: str
    ):
        self.db = HanaDB(
            connection=connection,
            embedding=embedding,
            table_name=table_name,
        )

    def retrieve(self, query: str) -> list[Document]:
        """Retrieve relevant documents based on the query."""
        docs = self.db.similarity_search(query, k=3)
        return docs
