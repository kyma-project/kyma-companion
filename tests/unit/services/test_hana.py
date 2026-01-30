from unittest.mock import MagicMock

import pytest

from routers.probes import IHanaConnection
from services.hana import Hana, get_hana


class TestHana:
    @pytest.mark.parametrize(
        "test_case, connection_factory, expected",
        [
            (
                "Connection created successfully",
                MagicMock(return_value=MagicMock()),
                True,
            ),
            (
                "Factory fails with exception",
                MagicMock(side_effect=Exception("Connection error")),
                False,
            ),
            ("No connection", MagicMock(return_value=None), False),
        ],
    )
    def test_is_hana_ready(self, test_case, connection_factory, expected):
        """
        Test the `is_connection_operational` method with various scenarios.

        This test verifies that the method returns the health status which is
        initially set based on whether connection creation succeeded.
        Background health checks will update this status during runtime.
        """
        # When:
        hana = Hana(connection_factory)
        result = hana.is_connection_operational()

        # Then:
        assert result == expected, f"Failed test case: {test_case}"

        # Clean up by resetting the instance.
        hana._reset_for_tests()

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test that health check passes when connection can execute queries."""
        # Given: Connection that can execute queries
        mock_cursor = MagicMock()
        mock_cursor.execute = MagicMock()
        mock_cursor.fetchone = MagicMock(return_value=(1,))
        mock_cursor.close = MagicMock()

        mock_connection = MagicMock()
        mock_connection.cursor = MagicMock(return_value=mock_cursor)

        connection_factory = MagicMock(return_value=mock_connection)

        # When:
        hana = Hana(connection_factory)
        result = await hana._execute_health_check()

        # Then:
        assert result is True
        mock_cursor.execute.assert_called_once_with("SELECT 1 FROM DUMMY")

        # Clean up
        hana._reset_for_tests()

    @pytest.mark.asyncio
    async def test_health_check_fails_on_query_error(self):
        """Test that health check fails when query execution throws error."""
        # Given: Connection that throws error on execute
        mock_cursor = MagicMock()
        mock_cursor.execute = MagicMock(side_effect=Exception("Password expired"))

        mock_connection = MagicMock()
        mock_connection.cursor = MagicMock(return_value=mock_cursor)

        connection_factory = MagicMock(return_value=mock_connection)

        # When:
        hana = Hana(connection_factory)
        result = await hana._execute_health_check()

        # Then:
        assert result is False

        # Clean up
        hana._reset_for_tests()

    def test_mark_unhealthy(self):
        """Test that mark_unhealthy sets health status to False."""
        # Given: Healthy connection
        mock_connection = MagicMock()
        connection_factory = MagicMock(return_value=mock_connection)

        hana = Hana(connection_factory)
        hana._health_status = True

        # When:
        hana.mark_unhealthy()

        # Then:
        assert hana._health_status is False
        assert hana.is_connection_operational() is False

        # Clean up
        hana._reset_for_tests()

    @pytest.mark.parametrize(
        "test_case, connection, expected",
        [
            ("No connection", None, False),
            ("Connection exists", MagicMock(spec=IHanaConnection), True),
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
