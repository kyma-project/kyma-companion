from unittest.mock import Mock, patch

import pytest
from hdbcli import dbapi
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from rag.retriever import HanaDBRetriever


@pytest.fixture
def mock_embeddings():
    """Create a mock embeddings model."""
    return Mock(spec=Embeddings)


@pytest.fixture
def mock_connection():
    """Create a mock HANA DB connection."""
    return Mock(spec=dbapi.Connection)


@pytest.fixture
def mock_hanadb():
    """Create a mock HanaDB instance."""
    with patch("rag.retriever.HanaDB") as mock:
        yield mock


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    with patch("rag.retriever.logger") as mock:
        yield mock


class TestHanaDBRetriever:
    """Test suite for HanaDBRetriever class."""

    def test_init(self, mock_embeddings, mock_connection, mock_hanadb):
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
        mock_hanadb.assert_called_once_with(
            connection=mock_connection,
            embedding=mock_embeddings,
            table_name=table_name,
        )
        assert retriever.db == mock_hanadb.return_value

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
    def test_retrieve(
        self,
        mock_embeddings,
        mock_connection,
        mock_hanadb,
        mock_logger,
        query,
        top_k,
        expected_docs,
        expected_error,
    ):
        """Test retrieve method."""
        # Given
        retriever = HanaDBRetriever(
            embedding=mock_embeddings,
            connection=mock_connection,
            table_name="test_table",
        )

        if expected_error:
            # Setup mock to raise exception
            mock_hanadb.return_value.similarity_search.side_effect = expected_error
            # When/Then
            with pytest.raises(type(expected_error)) as exc_info:
                retriever.retrieve(query, top_k)
            assert str(exc_info.value) == str(expected_error)
            mock_logger.exception.assert_called_once_with(
                f"Error retrieving documents for query: {query}"
            )
        else:
            # Setup mock to return expected documents
            mock_hanadb.return_value.similarity_search.return_value = expected_docs
            # When
            result = retriever.retrieve(query, top_k)
            # Then
            assert result == expected_docs
            mock_hanadb.return_value.similarity_search.assert_called_once_with(
                query, k=top_k
            )
