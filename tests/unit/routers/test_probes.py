from unittest.mock import MagicMock

import pytest

from routers.probes import is_hana_ready, is_redis_ready


@pytest.mark.parametrize(
    "test_case, connection, expected",
    [
        ("No connection", None, False),
        ("Connection ready", MagicMock(isconnected=MagicMock(return_value=True)), True),
        (
            "Connection not ready",
            MagicMock(isconnected=MagicMock(return_value=False)),
            False,
        ),
        (
            "Connection fails with exception",
            MagicMock(isconnected=MagicMock(side_effect=Exception("Connection error"))),
            False,
        ),
    ],
)
def test_is_hana_ready(test_case, connection, expected):
    """
    Test the `is_hana_ready` function with various scenarios.

    This test uses a table-driven approach to verify that the function
    correctly determines HANA readiness based on the connection state,
    `isconnected` result, and exceptions.
    """
    result = is_hana_ready(connection)
    assert result == expected, f"Failed test case: {test_case}"


@pytest.mark.parametrize(
    "test_case, connection, expected",
    [
        ("No connection", None, False),
        ("Connection ready", MagicMock(ping=MagicMock(return_value=True)), True),
        ("Connection not ready", MagicMock(ping=MagicMock(return_value=False)), False),
        (
            "Connection fails with exception",
            MagicMock(ping=MagicMock(side_effect=Exception("Connection error"))),
            False,
        ),
    ],
)
def test_is_redis_ready(test_case, connection, expected):
    """
    Test the `is_redis_ready` function with various scenarios.

    This test uses a table-driven approach to verify that the function
    correctly determines Redis readiness based on the connection state,
    `ping` result, and exceptions.
    """
    result = is_redis_ready(connection)
    assert result == expected, f"Failed test case: {test_case}"
