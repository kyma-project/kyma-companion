import time
from typing import Protocol

from hdbcli import dbapi
from langchain_hana import HanaDB
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.runnables import run_in_executor

from services.metrics import CustomMetrics
from utils.logging import get_logger

logger = get_logger(__name__)


class HanaVectorDB(HanaDB):
    """HANA DB Vector Store."""

    def __init__(
        self,
        connection: dbapi.Connection,
        embedding: Embeddings,
        table_name: str,
    ):
        super().__init__(connection, embedding, table_name=table_name)

    async def asimilarity_search(  # type: ignore[override]
        self, query: str, k: int = 4, filter: dict | None = None
    ) -> list[Document]:
        """Return docs most similar to query asynchronously

        Args:
            query: Text to look up documents similar to.
            k: Number of Documents to return. Defaults to 4.
            filter: A dictionary of metadata fields and values to filter by.
                    Defaults to None.

        Returns:
            List of Documents most similar to the query
        """

        try:
            result = await run_in_executor(
                None,
                self.similarity_search,
                query,
                k=k,
                filter=filter,
            )
            return result
        except Exception as e:
            raise e


class IRetriever(Protocol):
    """Retriever interface."""

    async def aretrieve(self, query: str, top_k: int = 3) -> list[Document]:
        """Retrieve relevant documents based on the query."""
        ...


class HanaDBRetriever:
    """HANA DB Retriever."""

    def __init__(
        self, embedding: Embeddings, connection: dbapi.Connection, table_name: str
    ):
        self.db = HanaVectorDB(
            connection=connection,
            embedding=embedding,
            table_name=table_name,
        )

    async def aretrieve(self, query: str, top_k: int = 5) -> list[Document]:
        """Retrieve relevant documents based on the query."""
        start_time = time.perf_counter()
        try:
            docs = await self.db.asimilarity_search(query, k=top_k)
            # record latency.
            await CustomMetrics().record_hanadb_latency(
                time.perf_counter() - start_time, True
            )
        except Exception as e:
            logger.exception(f"Error retrieving documents for query: {query}")
            await CustomMetrics().record_hanadb_latency(
                time.perf_counter() - start_time, False
            )
            raise e
        return docs
