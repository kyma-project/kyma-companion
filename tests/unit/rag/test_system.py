from unittest.mock import AsyncMock, Mock, patch

import pytest

from rag.query_generator import Queries
from rag.system import Query, RAGSystem
from unit.rag.reranker.fixtures import doc1, doc2, doc3
from utils.settings import (
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
        patch("rag.system.Hana"),
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
        # Given the default reranker mode
        monkeypatch.setattr("rag.system.RETRIEVAL_MODE", RetrievalMode.RERANKER)
        rag_system = RAGSystem(mock_models)
        top_k = 2
        candidate_k = 10  # max(top_k * 4, 10)
        expected_query_count = 2  # original query + one alternative
        expected_input_limit = 1000

        # When retrieving
        result = await rag_system.aretrieve(Query(text="What is Kyma?"), top_k=top_k)

        # Then the full pipeline runs: query rewrite -> multi-query retrieve -> LLM rerank
        collaborators["query_generator"].agenerate_queries.assert_awaited_once()
        retrieve_calls = collaborators["retriever"].aretrieve.await_args_list
        assert len(retrieve_calls) == expected_query_count
        assert all(call.kwargs["top_k"] == candidate_k for call in retrieve_calls)
        collaborators["reranker"].arerank.assert_awaited_once()
        rerank_kwargs = collaborators["reranker"].arerank.await_args.kwargs
        assert rerank_kwargs["input_limit"] == expected_input_limit
        assert rerank_kwargs["output_limit"] == top_k
        assert result == [doc1, doc2]

    @pytest.mark.asyncio
    async def test_default_mode_is_reranker(self, mock_models, collaborators):
        # Given no override, the module default applies
        rag_system = RAGSystem(mock_models)

        # When retrieving
        result = await rag_system.aretrieve(Query(text="What is Kyma?"), top_k=2)

        # Then the default is reranker and the reranking pipeline runs
        assert rag_system.mode == RetrievalMode.RERANKER
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
