from unittest.mock import MagicMock

import pytest

from routers.probes import IHanaConnection
from services.hana import Hana, get_hana


class TestHana:
    @pytest.mark.parametrize(
        "test_case, connection_factory, expected",
        [
            (
                "Connection ready",
                MagicMock(return_value=MagicMock(spec=IHanaConnection, isconnected=MagicMock(return_value=True))),
                True,
            ),
            (
                "Connection not ready",
                MagicMock(return_value=MagicMock(spec=IHanaConnection, isconnected=MagicMock(return_value=False))),
                False,
            ),
            (
                "Connection fails with exception",
                MagicMock(
                    return_value=MagicMock(
                        spec=IHanaConnection,
                        isconnected=MagicMock(side_effect=Exception("Connection error")),
                    )
                ),
                False,
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

        This test verifies that the method correctly determines Hana readiness
        based on the connection state, `isconnected` result, and exceptions.
        """
        # When:
        hana = Hana(connection_factory)
        result = hana.is_connection_operational()

        # Then:
        assert result == expected, f"Failed test case: {test_case}"

        # Clean up by resetting the instance.
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
