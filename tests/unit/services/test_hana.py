from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from hdbcli import dbapi

from services.hana import Hana, get_hana


class TestHana:
    @pytest.mark.parametrize(
        "test_case, cursor_behavior, expected",
        [
            (
                "Query executes successfully",
                {"execute": None, "fetchone": (1,)},
                True,
            ),
            (
                "Query execution fails",
                {"execute": Exception("Connection error")},
                False,
            ),
            (
                "Password expired error",
                {"execute": dbapi.Error(414, "user is forced to change password")},
                False,
            ),
            (
                "Fetchone fails",
                {"execute": None, "fetchone": Exception("Fetch error")},
                False,
            ),
        ],
    )
    def test_is_hana_ready_with_query(self, test_case, cursor_behavior, expected):
        """
        Test the `is_connection_operational` method executes test query.

        This test verifies that the method correctly determines Hana readiness
        by executing a SELECT query and handling various error scenarios.
        """
        # Given: Mock connection with cursor
        mock_cursor = MagicMock()

        if "execute" in cursor_behavior:
            if isinstance(cursor_behavior["execute"], Exception):
                mock_cursor.execute.side_effect = cursor_behavior["execute"]
            else:
                mock_cursor.execute.return_value = cursor_behavior["execute"]

        if "fetchone" in cursor_behavior:
            if isinstance(cursor_behavior["fetchone"], Exception):
                mock_cursor.fetchone.side_effect = cursor_behavior["fetchone"]
            else:
                mock_cursor.fetchone.return_value = cursor_behavior["fetchone"]

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        connection_factory = MagicMock(return_value=mock_connection)

        # When:
        hana = Hana(connection_factory)
        result = hana.is_connection_operational()

        # Then:
        assert result == expected, f"Failed test case: {test_case}"

        # Verify query was executed
        if expected or "execute" in cursor_behavior:
            mock_cursor.execute.assert_called_once_with("SELECT 1 FROM DUMMY")

        # Verify cursor was closed (only if connection exists)
        if "execute" in cursor_behavior or "fetchone" in cursor_behavior:
            mock_cursor.close.assert_called_once()

        # Clean up by resetting the instance.
        hana._reset_for_tests()

    def test_is_hana_ready_no_connection(self):
        """Test that is_connection_operational returns False when no connection."""
        # Given: No connection
        connection_factory = MagicMock(return_value=None)

        # When:
        hana = Hana(connection_factory)
        result = hana.is_connection_operational()

        # Then:
        assert result is False

        # Clean up
        hana._reset_for_tests()

    def test_is_hana_ready_connection_fails_during_init(self):
        """Test that is_connection_operational returns False when connection init fails."""
        # Given: Connection factory that raises exception
        connection_factory = MagicMock(side_effect=Exception("Connection error"))

        # When:
        hana = Hana(connection_factory)
        result = hana.is_connection_operational()

        # Then:
        assert result is False

        # Clean up
        hana._reset_for_tests()

    @pytest.mark.parametrize(
        "test_case, connection, expected",
        [
            ("No connection", None, False),
            ("Connection exists", MagicMock(), True),
        ],
    )
    def test_has_connection(self, test_case, connection, expected):
        """
        Test the `has_connection` method with various scenarios.

        Verifies that the method correctly determines if a connection exists.
        """

        # Given:
        connection_factory = MagicMock(return_value=connection)

        # When:
        hana = Hana(connection_factory)
        result = hana.has_connection()

        # Then:
        assert result == expected, f"Failed test case: {test_case}"

        # Clean up by resetting the instance.
        hana._reset_for_tests()

    def test_reset(self):
        """
        Test the `reset` method of the Hana class.

        This test verifies that the reset method clears the singleton instance
        and any associated resources.
        """

        # Given:
        # Create a new Hana instance.
        hana1 = get_hana()

        # When:
        hana1._reset_for_tests()
        hana2 = get_hana()

        # Then:
        assert hana1 != hana2

        hana2._reset_for_tests()

    def test_health_check_caching(self):
        """
        Test that is_connection_operational caches results within TTL.

        This test verifies that the health check result is cached and reused
        within the configured TTL, avoiding unnecessary database queries.
        """
        # Given: Mock connection with cursor
        mock_cursor = MagicMock()
        mock_cursor.execute.return_value = None
        mock_cursor.fetchone.return_value = (1,)

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        connection_factory = MagicMock(return_value=mock_connection)

        hana = Hana(connection_factory)

        # When & Then:
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        expected_query_count_after_cache_expiry = 2
        with patch("services.hana.datetime") as mock_datetime:
            # First call - should execute query
            mock_datetime.now.return_value = base_time
            result1 = hana.is_connection_operational()
            assert result1 is True
            assert mock_cursor.execute.call_count == 1

            # Second call within TTL - should use cache
            mock_datetime.now.return_value = base_time + timedelta(seconds=60)
            result2 = hana.is_connection_operational()
            assert result2 is True
            assert mock_cursor.execute.call_count == 1  # Still 1, cache was used

            # Third call after TTL expires - should execute query again
            mock_datetime.now.return_value = base_time + timedelta(seconds=301)
            result3 = hana.is_connection_operational()
            assert result3 is True
            assert mock_cursor.execute.call_count == expected_query_count_after_cache_expiry

        # Clean up
        hana._reset_for_tests()

    def test_health_check_caches_failure_state(self):
        """
        Test that is_connection_operational caches failure state as well.

        This ensures that failed health checks are also cached to avoid
        hammering the database with repeated failing queries.
        """
        # Given: Mock connection that fails
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Connection error")

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor
        connection_factory = MagicMock(return_value=mock_connection)

        hana = Hana(connection_factory)

        # When & Then:
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        with patch("services.hana.datetime") as mock_datetime:
            # First call - should execute query and fail
            mock_datetime.now.return_value = base_time
            result1 = hana.is_connection_operational()
            assert result1 is False
            assert mock_cursor.execute.call_count == 1

            # Second call within TTL - should use cached failure state
            mock_datetime.now.return_value = base_time + timedelta(seconds=60)
            result2 = hana.is_connection_operational()
            assert result2 is False
            assert mock_cursor.execute.call_count == 1  # Still 1, cache was used

        # Clean up
        hana._reset_for_tests()
