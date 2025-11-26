import asyncio
import os
from typing import Protocol, cast

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel

from rag.document_grounding_retriever import DocumentGroundingRetriever
from rag.query_generator import QueryGenerator
from rag.reranker.reranker import LLMReranker
from utils.logging import get_logger
from utils.models.factory import IModel
from utils.settings import (
    DOCS_TABLE_NAME,
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
        self.query_generator = QueryGenerator(
            cast(IModel, cast(IModel, models[MAIN_MODEL_MINI_NAME]))
        )
        # setup retriever
        # self.retriever = HanaDBRetriever(
        #     embedding=cast(Embeddings, models[MAIN_EMBEDDING_MODEL_NAME]),
        #     connection=Hana().get_connction(),
        #     table_name=DOCS_TABLE_NAME,
        # )

        self.retriever = DocumentGroundingRetriever(
            api_url=str(os.getenv("AICORE_BASE_URL")),
            client_id=str(os.getenv("AICORE_CLIENT_ID")),
            client_secret=str(os.getenv("AICORE_CLIENT_SECRET")),
            token_url=str(os.getenv("AICORE_AUTH_URL")),
            resource_group="document-grounding",
            data_repository_type="help.sap.com",
            filter_id="string",
        )

        # setup reranker
        self.reranker = LLMReranker(cast(IModel, models[MAIN_MODEL_MINI_NAME]))

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
