import asyncio
from typing import Protocol, cast

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel

from rag.generator import Generator
from rag.query_generator import QueryGenerator
from rag.retriever import HanaDBRetriever
from utils.hana import create_hana_connection
from utils.logging import get_logger
from utils.models.factory import IModel, ModelType
from utils.settings import (
    DATABASE_PASSWORD,
    DATABASE_PORT,
    DATABASE_URL,
    DATABASE_USER,
    DOCS_TABLE_NAME,
)

logger = get_logger(__name__)


class Query(BaseModel):
    """A RAG system query."""

    text: str


class IRAGSystem(Protocol):
    """A protocol for a RAG system."""

    async def aretrieve(self, query: Query, top_k: int = 5) -> list[Document]:
        """Retrieve documents for a given query."""
        ...

    async def agenerate(
        self,
        query: Query,
        relevant_docs: list[Document],
    ) -> str:
        """Generate a response to a given query."""
        ...


class RAGSystem:
    """A system that can be used to generate queries and retrieve documents."""

    def __init__(self, models: dict[str, IModel | Embeddings]):
        # setup query generator
        self.query_generator = QueryGenerator(
            cast(IModel, cast(IModel, models[ModelType.GPT4O_MINI]))
        )
        # setup retriever
        hana_conn = create_hana_connection(
            DATABASE_URL, DATABASE_PORT, DATABASE_USER, DATABASE_PASSWORD
        )
        self.retriever = HanaDBRetriever(
            embedding=cast(Embeddings, models[ModelType.TEXT_EMBEDDING_3_LARGE]),
            connection=hana_conn,
            table_name=DOCS_TABLE_NAME,
        )
        # setup generator
        self.generator = Generator(cast(IModel, models[ModelType.GPT4O_MINI]))

        logger.info("RAG system initialized.")
        logger.debug(f"Hana DB table name: {DOCS_TABLE_NAME}")

    @staticmethod
    def _remove_duplicates(documents: list[Document]) -> list[Document]:
        """Remove duplicate documents based on content."""
        seen_content = set()
        unique_docs = []

        for doc in documents:
            if doc.page_content not in seen_content:
                seen_content.add(doc.page_content)
                unique_docs.append(doc)

        return unique_docs

    async def aretrieve(self, query: Query, top_k: int = 5) -> list[Document]:
        """Retrieve documents for a given query."""
        logger.info(f"Retrieving documents for query: {query.text}")

        alternative_queries = await self.query_generator.agenerate_queries(query.text)
        # add original query to the list
        all_queries = [query.text] + alternative_queries.queries

        # retrieve documents for all queries concurrently
        docs_lists = await asyncio.gather(
            *(self.retriever.aretrieve(q) for q in all_queries)
        )
        # remove duplicates from all retrieved documents
        all_docs = self._remove_duplicates([doc for docs in docs_lists for doc in docs])

        # TODO: re-rank documents

        if len(all_docs) > top_k:
            all_docs = all_docs[:top_k]

        logger.info(f"Retrieved {len(all_docs)} documents.")
        return all_docs

    async def agenerate(
        self,
        query: Query,
        relevant_docs: list[Document],
    ) -> str:
        """Generate a response to a given query."""
        return await self.generator.agenerate(relevant_docs, query.text)
