from unittest.mock import MagicMock, patch

import pytest
from hdbcli import dbapi

from rag.system import RAGSystem
from services.hana import Hana


class TestRAGSystem:
    """Test suite for RAGSystem class."""

    def teardown_method(self):
        """Clean up after each test to reset Hana singleton."""
        Hana._reset_for_tests()

    def test_init_marks_unhealthy_on_hana_error(self):
        """Test that RAGSystem initialization marks connection unhealthy on HANA errors."""
        # Given
        mock_models = {
            "gpt-4o-mini": MagicMock(),
            "text-embedding-3-large": MagicMock(),
        }

        # Mock Hana to raise an error
        with patch("rag.system.Hana") as mock_hana_class:
            mock_hana_instance = MagicMock()
            mock_hana_class.return_value = mock_hana_instance
            mock_hana_instance.get_connction.side_effect = dbapi.Error(414, "user is forced to change password")

            # When/Then
            with pytest.raises(dbapi.Error):
                RAGSystem(mock_models)

            # Verify mark_unhealthy was called
            mock_hana_instance.mark_unhealthy.assert_called_once()

    def test_init_marks_unhealthy_on_retriever_error(self):
        """Test that RAGSystem marks connection unhealthy when HanaDBRetriever init fails."""
        # Given
        mock_models = {
            "gpt-4o-mini": MagicMock(),
            "text-embedding-3-large": MagicMock(),
        }

        with patch("rag.system.Hana") as mock_hana_class, patch("rag.system.HanaDBRetriever") as mock_retriever_class:
            mock_hana_instance = MagicMock()
            mock_hana_class.return_value = mock_hana_instance
            mock_hana_instance.get_connction.return_value = MagicMock()

            # HanaDBRetriever raises error during initialization
            mock_retriever_class.side_effect = Exception("Table does not exist")

            # When/Then
            with pytest.raises(Exception, match="Table does not exist"):
                RAGSystem(mock_models)

            # Verify mark_unhealthy was called
            mock_hana_instance.mark_unhealthy.assert_called_once()
