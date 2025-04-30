import asyncio
from typing import Protocol, cast

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel

from rag.generator import Generator
from rag.query_generator import QueryGenerator
from rag.reranker.reranker import LLMReranker
from rag.retriever import HanaDBRetriever
from services.hana import get_hana_connection
from utils.logging import get_logger
from utils.models.factory import IModel, ModelType
from utils.settings import (
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
        hana_conn = next(get_hana_connection()).connection
        if hana_conn is None:
            raise ValueError("Failed to establish a HANA connection.")

        # setup retriever
        self.retriever = HanaDBRetriever(
            embedding=cast(Embeddings, models[ModelType.TEXT_EMBEDDING_3_LARGE]),
            connection=hana_conn,
            table_name=DOCS_TABLE_NAME,
        )
        # setup generator
        self.generator = Generator(cast(IModel, models[ModelType.GPT4O_MINI]))

        # setup reranker
        self.reranker = LLMReranker(cast(IModel, models[ModelType.GPT4O_MINI]))

        logger.info("RAG system initialized.")
        logger.debug(f"Hana DB table name: {DOCS_TABLE_NAME}")

    async def aretrieve(self, query: Query, top_k: int = 5) -> list[Document]:
        """Retrieve documents for a given query."""
        logger.info(f"Retrieving documents for query: {query.text}")

        alternative_queries = await self.query_generator.agenerate_queries(query.text)
        # add original query to the list
        all_queries = [query.text] + alternative_queries.queries

        # retrieve documents for all queries concurrently
        all_docs = await asyncio.gather(
            *(self.retriever.aretrieve(q) for q in all_queries)
        )

        # rerank documents
        reranked_docs = await self.reranker.arerank(
            all_docs,
            all_queries,
            input_limit=1000,
            output_limit=top_k,
        )

        logger.info(f"Retrieved {len(reranked_docs)} documents.")
        return reranked_docs

    async def agenerate(
        self,
        query: Query,
        relevant_docs: list[Document],
    ) -> str:
        """Generate a response to a given query."""
        return await self.generator.agenerate(relevant_docs, query.text)
