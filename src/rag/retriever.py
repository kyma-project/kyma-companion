from typing import Protocol

from hdbcli import dbapi
from langchain_community.vectorstores import HanaDB
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel

from utils.logging import get_logger

logger = get_logger(__name__)


class Query(BaseModel):
    """A RAG system query."""

    text: str


class IRetriever(Protocol):
    """Retriever interface."""

    def retrieve(self, query: Query, top_k: int = 3) -> list[Document]:
        """Retrieve relevant documents based on the query."""
        ...


class HanaDBRetriever:
    """HANA DB Retriever."""

    def __init__(
        self, embedding: Embeddings, connection: dbapi.Connection, table_name: str
    ):
        self.db = HanaDB(
            connection=connection,
            embedding=embedding,
            table_name=table_name,
        )

    def retrieve(self, query: str, top_k: int = 5) -> list[Document]:
        """Retrieve relevant documents based on the query."""
        try:
            docs = self.db.similarity_search(query, k=top_k)
        except Exception as e:
            logger.exception(f"Error retrieving documents for query: {query}")
            raise e
        return docs
