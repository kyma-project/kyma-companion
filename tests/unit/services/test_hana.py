from unittest.mock import MagicMock, patch

import pytest

from services.hana import get_hana_connection


class TestHana:
    @pytest.fixture(autouse=True)
    def mock_connection(self):
        with patch("services.hana.dbapi.Connection") as mock:
            mock = MagicMock()
            yield mock

    @pytest.mark.parametrize(
        "test_case, connection, expected",
        [
            ("No connection", None, False),
            (
                "Connection ready",
                MagicMock(isconnected=MagicMock(return_value=True)),
                True,
            ),
            (
                "Connection not ready",
                MagicMock(isconnected=MagicMock(return_value=False)),
                False,
            ),
            (
                "Connection fails with exception",
                MagicMock(
                    isconnected=MagicMock(side_effect=Exception("Connection error"))
                ),
                False,
            ),
        ],
    )
    def test_is_hana_ready(self, test_case, connection, expected):
        """
        Test the `is_connection_operational` method with various scenarios.

        This test verifies that the method correctly determines Hana readiness
        based on the connection state, `isconnected` result, and exceptions.
        """
        # Given:
        # Create a new hana instance.
        hana = get_hana_connection()
        hana.connection = connection
        result = hana.is_connection_operational()

        assert result == expected, f"Failed test case: {test_case}"

        # Clean up by resetting the Redis instance.
        hana.reset()

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
        # Create a new redis instance.
        hana = get_hana_connection()
        # Replace the connection with prepared fixtures.
        hana.connection = connection

        # When:
        result = hana.has_connection()

        # Then:
        assert result == expected, f"Failed test case: {test_case}"

        # Clean up by resetting the Redis instance.
        hana.reset()

    def test_reset(self):
        """
        Test the `reset` method of the Hana class.

        This test verifies that the reset method clears the singleton instance
        and any associated resources.
        """

        # Given:
        # Create a new Hana instance.
        hana1 = get_hana_connection()

        # When:
        hana1.reset()
        hana2 = get_hana_connection()

        # Then:
        assert hana1 != hana2
