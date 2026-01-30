from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from hdbcli import dbapi
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from rag.retriever import HanaDBRetriever
from services.metrics import HANADB_LATENCY_METRIC_KEY, CustomMetrics


@pytest.fixture
def mock_embeddings():
    """Create a mock embeddings model."""
    return Mock(spec=Embeddings)


@pytest.fixture
def mock_connection():
    """Create a mock HANA DB connection."""
    return Mock(spec=dbapi.Connection)


@pytest.fixture
def mock_hanavectordb():
    """Create a mock HanaVectorDB instance."""
    with patch("rag.retriever.HanaVectorDB") as mock:
        # Set up the async method
        mock.return_value.asimilarity_search = AsyncMock()
        yield mock


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    with patch("rag.retriever.logger") as mock:
        yield mock


class TestHanaDBRetriever:
    """Test suite for HanaDBRetriever class."""

    def test_init(self, mock_embeddings, mock_connection, mock_hanavectordb):
        """Test HanaDBRetriever initialization."""
        # Given
        table_name = "test_table"

        # When
        retriever = HanaDBRetriever(
            embedding=mock_embeddings,
            connection=mock_connection,
            table_name=table_name,
        )

        # Then
        mock_hanavectordb.assert_called_once_with(
            connection=mock_connection,
            embedding=mock_embeddings,
            table_name=table_name,
        )
        assert retriever.db == mock_hanavectordb.return_value

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "query, top_k, expected_docs, expected_error",
        [
            # Test case: Successful retrieval
            (
                "test query",
                3,
                [
                    Document(page_content="doc1"),
                    Document(page_content="doc2"),
                    Document(page_content="doc3"),
                ],
                None,
            ),
            # Test case: Empty result
            (
                "no results query",
                5,
                [],
                None,
            ),
            # Test case: Error during retrieval
            (
                "error query",
                3,
                None,
                Exception("Database error"),
            ),
        ],
    )
    async def test_aretrieve(
        self,
        mock_embeddings,
        mock_connection,
        mock_hanavectordb,
        mock_logger,
        query,
        top_k,
        expected_docs,
        expected_error,
    ):
        """Test aretrieve method."""
        # Given
        retriever = HanaDBRetriever(
            embedding=mock_embeddings,
            connection=mock_connection,
            table_name="test_table",
        )

        metric_name = f"{HANADB_LATENCY_METRIC_KEY}_count"

        if expected_error:
            before_failure_metric_value = CustomMetrics().registry.get_sample_value(
                metric_name, {"is_success": "False"}
            )
            if before_failure_metric_value is None:
                before_failure_metric_value = 0
            # Setup mock to raise exception
            mock_hanavectordb.return_value.asimilarity_search.side_effect = expected_error
            # When/Then
            with pytest.raises(type(expected_error)) as exc_info:
                await retriever.aretrieve(query, top_k)
            assert str(exc_info.value) == str(expected_error)
            mock_logger.exception.assert_called_once_with(f"Error retrieving documents for query: {query}")
            # check metric.
            after_failure_metric_value = CustomMetrics().registry.get_sample_value(metric_name, {"is_success": "False"})
            assert after_failure_metric_value > before_failure_metric_value
        else:
            before_success_metric_value = CustomMetrics().registry.get_sample_value(metric_name, {"is_success": "True"})
            if before_success_metric_value is None:
                before_success_metric_value = 0
            # Setup mock to return expected documents
            mock_hanavectordb.return_value.asimilarity_search.return_value = expected_docs
            # When
            result = await retriever.aretrieve(query, top_k)
            # Then
            assert result == expected_docs
            mock_hanavectordb.return_value.asimilarity_search.assert_called_once_with(query, k=top_k)
            # check metric.
            after_success_metric_value = CustomMetrics().registry.get_sample_value(metric_name, {"is_success": "True"})
            assert after_success_metric_value > before_success_metric_value

    @pytest.mark.asyncio
    async def test_aretrieve_marks_unhealthy_on_error(
        self, mock_embeddings, mock_connection, mock_hanavectordb, mock_logger
    ):
        """Test that aretrieve marks connection unhealthy on database errors."""
        # Given
        retriever = HanaDBRetriever(
            embedding=mock_embeddings,
            connection=mock_connection,
            table_name="test_table",
        )
        mock_hanavectordb.return_value.asimilarity_search.side_effect = dbapi.Error(
            414, "user is forced to change password"
        )

        # Mock the Hana singleton
        with patch("rag.retriever.Hana") as mock_hana_class:
            mock_hana_instance = MagicMock()
            mock_hana_class.return_value = mock_hana_instance

            # When
            with pytest.raises(dbapi.Error):
                await retriever.aretrieve("test query", 5)

            # Then
            mock_hana_instance.mark_unhealthy.assert_called_once()
