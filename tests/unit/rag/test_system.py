import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest

from rag.current_run import NoCurrentRunError
from rag.query_generator import Queries
from rag.system import _RERANKER_INPUT_LIMIT, Query, RAGSystem
from unit.rag.fakes import FakeClock, FakeConnection, make_retriever
from unit.rag.reranker.fixtures import doc1, doc2, doc3
from utils.settings import (
    DOCS_CORPUS,
    DOCS_RUN_CACHE_TTL_SECONDS,
    DOCS_RUNS_TABLE,
    MAIN_EMBEDDING_MODEL_NAME,
    MAIN_MODEL_MINI_NAME,
    RAG_NUM_QUERIES,
    RetrievalMode,
)


@pytest.fixture
def mock_models():
    """Models dict keyed as RAGSystem expects."""
    return {
        MAIN_MODEL_MINI_NAME: Mock(),
        MAIN_EMBEDDING_MODEL_NAME: Mock(),
    }


@pytest.fixture
def collaborators():
    """Patch RAGSystem's collaborators so no real DB/LLM is touched."""
    with (
        patch("rag.system.Hana") as hana_cls,
        patch("rag.system.CurrentRunTable") as current_run_cls,
        patch("rag.system.HanaDBRetriever") as retriever_cls,
        patch("rag.system.QueryGenerator") as query_generator_cls,
        patch("rag.system.LLMReranker") as reranker_cls,
    ):
        retriever = retriever_cls.return_value
        retriever.aretrieve = AsyncMock(return_value=[doc1, doc2, doc3])
        query_generator = query_generator_cls.return_value
        query_generator.agenerate_queries = AsyncMock(return_value=Queries(queries=["alt query"]))
        reranker = reranker_cls.return_value
        reranker.arerank = AsyncMock(return_value=[doc1, doc2])
        yield {
            "connection": hana_cls.return_value.get_connction.return_value,
            "current_run_cls": current_run_cls,
            "retriever_cls": retriever_cls,
            "retriever": retriever,
            "query_generator": query_generator,
            "query_generator_cls": query_generator_cls,
            "reranker": reranker,
        }


class TestRAGSystemMode:
    """RAGSystem selects its retrieval pipeline from the configured mode."""

    def test_init_reads_configured_mode(self, monkeypatch, mock_models, collaborators):
        # Given the fusion mode is configured
        monkeypatch.setattr("rag.system.RETRIEVAL_MODE", RetrievalMode.FUSION)

        # When the RAG system is initialized
        rag_system = RAGSystem(mock_models)

        # Then the mode is fixed on the instance
        assert rag_system.mode == RetrievalMode.FUSION

    def test_query_generator_uses_configured_num_queries(self, mock_models, collaborators):
        # When the RAG system is initialized
        RAGSystem(mock_models)

        # Then the query generator is built with the configured number of alternative queries
        assert collaborators["query_generator_cls"].call_args.kwargs["num_queries"] == RAG_NUM_QUERIES

    @pytest.mark.asyncio
    async def test_reranker_mode(self, monkeypatch, mock_models, collaborators):
        # Given the reranker mode
        monkeypatch.setattr("rag.system.RETRIEVAL_MODE", RetrievalMode.RERANKER)
        rag_system = RAGSystem(mock_models)
        top_k = 2
        candidate_k = 10  # max(top_k * 4, 10)
        expected_query_count = 2  # original query + one alternative

        # When retrieving
        result = await rag_system.aretrieve(Query(text="What is Kyma?"), top_k=top_k)

        # Then the full pipeline runs: query rewrite -> multi-query retrieve -> LLM rerank
        collaborators["query_generator"].agenerate_queries.assert_awaited_once()
        retrieve_calls = collaborators["retriever"].aretrieve.await_args_list
        assert len(retrieve_calls) == expected_query_count
        assert all(call.kwargs["top_k"] == candidate_k for call in retrieve_calls)
        collaborators["reranker"].arerank.assert_awaited_once()
        rerank_kwargs = collaborators["reranker"].arerank.await_args.kwargs
        assert rerank_kwargs["input_limit"] == _RERANKER_INPUT_LIMIT
        assert rerank_kwargs["output_limit"] == top_k
        assert result == [doc1, doc2]

    @pytest.mark.asyncio
    async def test_default_mode_is_reranker(self, monkeypatch, mock_models, collaborators):
        # Given the default mode (reranker) is explicitly set for isolation
        monkeypatch.setattr("rag.system.RETRIEVAL_MODE", RetrievalMode.RERANKER)
        rag_system = RAGSystem(mock_models)

        # When retrieving
        result = await rag_system.aretrieve(Query(text="What is Kyma?"), top_k=2)

        # Then the default is reranker: query rewrite -> multi-query retrieve -> LLM rerank
        assert rag_system.mode == RetrievalMode.RERANKER
        collaborators["query_generator"].agenerate_queries.assert_awaited_once()
        collaborators["reranker"].arerank.assert_awaited_once()
        assert result == [doc1, doc2]

    @pytest.mark.asyncio
    async def test_vector_mode_skips_rewrite_and_rerank(self, monkeypatch, mock_models, collaborators):
        # Given the vector mode
        monkeypatch.setattr("rag.system.RETRIEVAL_MODE", RetrievalMode.VECTOR)
        rag_system = RAGSystem(mock_models)

        # When retrieving
        result = await rag_system.aretrieve(Query(text="What is Kyma?"), top_k=5)

        # Then a single similarity search runs, without query rewrite or reranking
        collaborators["retriever"].aretrieve.assert_awaited_once_with("What is Kyma?", top_k=5)
        collaborators["query_generator"].agenerate_queries.assert_not_awaited()
        collaborators["reranker"].arerank.assert_not_awaited()
        assert result == [doc1, doc2, doc3]

    @pytest.mark.asyncio
    async def test_fusion_mode_uses_rrf_not_reranker(self, monkeypatch, mock_models, collaborators):
        # Given the fusion mode
        monkeypatch.setattr("rag.system.RETRIEVAL_MODE", RetrievalMode.FUSION)
        rag_system = RAGSystem(mock_models)
        top_k = 3
        candidate_k = 12  # max(top_k * 4, 10)
        expected_query_count = 2  # original query + one alternative

        # When retrieving, with RRF stubbed to observe the call
        with patch("rag.system.get_relevant_documents", return_value=[doc1]) as mock_rrf:
            result = await rag_system.aretrieve(Query(text="What is Kyma?"), top_k=top_k)

        # Then query rewrite runs, RRF fuses the candidates, and the LLM reranker is not used
        collaborators["query_generator"].agenerate_queries.assert_awaited_once()
        retrieve_calls = collaborators["retriever"].aretrieve.await_args_list
        assert len(retrieve_calls) == expected_query_count
        assert all(call.kwargs["top_k"] == candidate_k for call in retrieve_calls)
        collaborators["reranker"].arerank.assert_not_awaited()
        mock_rrf.assert_called_once()
        # RRF receives one candidate list per query and the top_k limit
        assert len(mock_rrf.call_args.args[0]) == expected_query_count
        assert mock_rrf.call_args.kwargs["limit"] == top_k
        assert result == [doc1]


class TestRAGSystemCurrentRun:
    """RAGSystem reads the table of the current run of the corpus, never a fixed table."""

    def test_init_uses_run_table_of_corpus(self, mock_models, collaborators):
        # When the RAG system is initialized
        RAGSystem(mock_models)

        # Then the retriever resolves the current run of the configured corpus in the run table
        collaborators["current_run_cls"].assert_called_once_with(
            collaborators["connection"],
            corpus=DOCS_CORPUS,
            runs_table=DOCS_RUNS_TABLE,
            ttl_seconds=DOCS_RUN_CACHE_TTL_SECONDS,
        )
        retriever_kwargs = collaborators["retriever_cls"].call_args.kwargs
        assert retriever_kwargs["current_run"] == collaborators["current_run_cls"].return_value
        assert "table_name" not in retriever_kwargs

    def test_init_resolves_current_run_once(self, mock_models, collaborators):
        # When the RAG system is initialized
        rag_system = RAGSystem(mock_models)

        # Then the current run is resolved at startup
        rag_system.retriever.current_run.resolve.assert_called_once_with()

    def test_init_fails_without_current_run(self, mock_models, collaborators):
        # Given the corpus has no current run
        collaborators["retriever"].current_run.resolve.side_effect = NoCurrentRunError(
            "corpus kyma_docs has no current run in docs_index_runs"
        )

        # When/Then the RAG system cannot start
        with pytest.raises(NoCurrentRunError, match="corpus kyma_docs has no current run in docs_index_runs"):
            RAGSystem(mock_models)


class FakeQueryGenerator:
    def __init__(self) -> None:
        self.calls = 0

    async def agenerate_queries(self, query: str):
        self.calls += 1
        raise AssertionError("query generation must not run without a current run")


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", list(RetrievalMode))
async def test_rag_system_fails_fast_without_current_run(fake_db, caplog, mode):
    # Given a RAG system whose corpus lost its current run after startup
    system = object.__new__(RAGSystem)
    system.corpus = "ops_docs"
    system.mode = mode
    system.query_generator = FakeQueryGenerator()  # type: ignore[assignment]
    system.retriever = make_retriever(FakeConnection(None), FakeClock())

    # When/Then retrieval fails before any LLM call, logged without traceback
    with (
        caplog.at_level(logging.INFO),
        pytest.raises(NoCurrentRunError, match="corpus ops_docs has no current run in docs_index_runs"),
    ):
        await system.aretrieve(Query(text="q"))

    assert system.query_generator.calls == 0  # type: ignore[attr-defined]
    expected = "No usable current run of corpus ops_docs in run table docs_index_runs; cannot search."
    assert any(r.getMessage() == expected for r in caplog.records)
    assert all(r.exc_info is None for r in caplog.records)
