import asyncio
from typing import Protocol, cast

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel

from rag.query_generator import QueryGenerator
from rag.reranker.reranker import LLMReranker
from rag.retriever import HanaDBRetriever
from services.hana import Hana
from utils.logging import get_logger
from utils.models.factory import IModel
from utils.settings import (
    DOCS_TABLE_NAME,
    MAIN_EMBEDDING_MODEL_NAME,
    MAIN_MODEL_MINI_NAME,
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


class RAGSystem:
    """A system that can be used to generate queries and retrieve documents."""

    def __init__(self, models: dict[str, IModel | Embeddings]):
        # setup query generator
        self.query_generator = QueryGenerator(cast(IModel, cast(IModel, models[MAIN_MODEL_MINI_NAME])))
        # setup retriever
        self.retriever = HanaDBRetriever(
            embedding=cast(Embeddings, models[MAIN_EMBEDDING_MODEL_NAME]),
            connection=Hana().get_connction(),
            table_name=DOCS_TABLE_NAME,
        )

        # setup reranker
        self.reranker = LLMReranker(cast(IModel, models[MAIN_MODEL_MINI_NAME]))

        logger.info("RAG system initialized.")
        logger.debug(f"Hana DB table name: {DOCS_TABLE_NAME}")

    async def aretrieve(self, query: Query, top_k: int = 5) -> list[Document]:
        """Retrieve documents for a given query."""
        logger.info(f"Retrieving documents for query: {query.text}")

        alternative_queries = await self.query_generator.agenerate_queries(query.text)

        # add original query to the list and de-duplicate
        raw_queries = [query.text] + alternative_queries.queries
        seen: set[str] = set()
        all_queries: list[str] = []
        for q in raw_queries:
            q = (q or "").strip()
            if not q or q in seen:
                continue
            seen.add(q)
            all_queries.append(q)

        # retrieve a larger candidate set per query for reranking
        candidate_k = max(top_k * 4, 10)

        # retrieve documents for all queries concurrently
        all_docs = await asyncio.gather(
            *(
                self.retriever.aretrieve(
                    q,
                    top_k=candidate_k,
                )
                for q in all_queries
            )
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
