import asyncio
from typing import cast

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.runnables import run_in_executor
from pydantic import BaseModel

from rag.current_run import CurrentRunTable, RunTableError
from rag.query_generator import QueryGenerator
from rag.reranker.reranker import LLMReranker
from rag.reranker.rrf import get_relevant_documents
from rag.retriever import HanaDBRetriever
from services.hana import Hana
from utils.logging import get_logger
from utils.models.factory import IModel
from utils.settings import (
    DOCS_CORPUS,
    DOCS_RUN_CACHE_TTL_SECONDS,
    DOCS_RUNS_TABLE,
    MAIN_EMBEDDING_MODEL_NAME,
    MAIN_MODEL_MINI_NAME,
    RAG_NUM_QUERIES,
    RETRIEVAL_MODE,
    RetrievalMode,
)

logger = get_logger(__name__)

_RERANKER_INPUT_LIMIT = 1000  # max candidate docs passed to the LLM reranker


class Query(BaseModel):
    """A RAG system query."""

    text: str


class RAGSystem:
    """A system that can be used to generate queries and retrieve documents.

    The retrieval strategy is fixed at construction time via the RETRIEVAL_MODE setting.
    The docs table is the one of the current run of ``corpus`` in the run table
    DOCS_RUNS_TABLE, resolved per request (cached for DOCS_RUN_CACHE_TTL_SECONDS).
    """

    def __init__(self, models: dict[str, IModel | Embeddings], corpus: str = DOCS_CORPUS):
        self.corpus = corpus
        # setup query generator
        self.query_generator = QueryGenerator(
            cast(IModel, models[MAIN_MODEL_MINI_NAME]),
            num_queries=RAG_NUM_QUERIES,
        )
        # setup retriever over the table of the current run of the corpus
        connection = Hana().get_connction()
        self.retriever = HanaDBRetriever(
            embedding=cast(Embeddings, models[MAIN_EMBEDDING_MODEL_NAME]),
            connection=connection,
            current_run=CurrentRunTable(
                connection,
                corpus=corpus,
                runs_table=DOCS_RUNS_TABLE,
                ttl_seconds=DOCS_RUN_CACHE_TTL_SECONDS,
            ),
        )
        # Fail at startup when the corpus has no usable current run: the error names
        # the corpus and the run table. There is no fallback to a fixed table.
        self.retriever.current_run.resolve()

        # setup reranker
        self.reranker = LLMReranker(cast(IModel, models[MAIN_MODEL_MINI_NAME]))

        # retrieval strategy is fixed at startup via the RETRIEVAL_MODE setting
        self.mode = RETRIEVAL_MODE

        logger.info(f"RAG system initialized with retrieval mode: {self.mode}.")
        logger.debug(f"Corpus: {corpus}, run table: {DOCS_RUNS_TABLE}")

    async def aretrieve(self, query: Query, top_k: int = 5) -> list[Document]:
        """Retrieve documents for a given query using the configured retrieval mode."""
        logger.info(f"Retrieving documents for query: {query.text} (mode: {self.mode})")

        # Fail fast without the LLM call if the corpus has no usable current run.
        try:
            await run_in_executor(None, self.retriever.current_run.resolve)
        except RunTableError:
            # A state of the run table, not a bug: no traceback, no exception text.
            logger.error(
                f"No usable current run of corpus {self.retriever.current_run.corpus} in run table "
                f"{self.retriever.current_run.runs_table}; cannot search."
            )
            raise

        if self.mode == RetrievalMode.VECTOR:
            return await self._aretrieve_vector(query, top_k)
        if self.mode == RetrievalMode.FUSION:
            return await self._aretrieve_fusion(query, top_k)
        if self.mode == RetrievalMode.RERANKER:
            return await self._aretrieve_reranker(query, top_k)
        raise ValueError(f"Unknown retrieval mode: {self.mode}")

    async def _aretrieve_vector(self, query: Query, top_k: int) -> list[Document]:
        """Single embedding similarity search: no query rewrite, no reranking."""
        docs = await self.retriever.aretrieve(query.text, top_k=top_k)
        logger.info(f"Retrieved {len(docs)} documents (vector).")
        return docs

    async def _aretrieve_fusion(self, query: Query, top_k: int) -> list[Document]:
        """Multi-query retrieval fused with Reciprocal Rank Fusion, deduplicated by content."""
        _, all_docs = await self._gather_multi_query_docs(query, top_k)
        fused_docs = get_relevant_documents(all_docs, limit=top_k)
        logger.info(f"Retrieved {len(fused_docs)} documents (fusion).")
        return fused_docs

    async def _aretrieve_reranker(self, query: Query, top_k: int) -> list[Document]:
        """Multi-query retrieval followed by LLM reranking (default pipeline)."""
        all_queries, all_docs = await self._gather_multi_query_docs(query, top_k)
        reranked_docs = await self.reranker.arerank(
            all_docs,
            all_queries,
            input_limit=_RERANKER_INPUT_LIMIT,
            output_limit=top_k,
        )
        logger.info(f"Retrieved {len(reranked_docs)} documents (reranker).")
        return reranked_docs

    async def _gather_multi_query_docs(self, query: Query, top_k: int) -> tuple[list[str], list[list[Document]]]:
        """Rewrite the query into alternatives and retrieve a candidate set for each, concurrently."""
        alternative_queries = await self.query_generator.agenerate_queries(query.text)

        # add original query to the list, filter empty queries, and de-duplicate
        raw_queries = [query.text] + alternative_queries.queries
        seen: set[str] = set()
        all_queries: list[str] = []
        for q in raw_queries:
            q = (q or "").strip()
            if not q or q in seen:
                continue
            seen.add(q)
            all_queries.append(q)

        # retrieve a larger candidate set per query for fusion/reranking
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
        return all_queries, list(all_docs)
