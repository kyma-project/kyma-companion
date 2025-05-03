from unittest.mock import MagicMock, patch

import pytest

from services.redis import get_redis_connection


class TestRedis:
    @pytest.fixture(autouse=True)
    def mock_connection(self):
        with patch("services.redis.AsyncRedis") as mock:
            mock = MagicMock()
            yield mock

    @pytest.mark.parametrize(
        "test_case, connection, expected",
        [
            ("No connection", None, False),
            ("Connection ready", MagicMock(ping=MagicMock(return_value=True)), True),
            (
                "Connection not ready",
                MagicMock(ping=MagicMock(return_value=False)),
                False,
            ),
            (
                "Connection fails with exception",
                MagicMock(ping=MagicMock(side_effect=Exception("Connection error"))),
                False,
            ),
        ],
    )
    def test_is_connection_operational(self, test_case, connection, expected):
        """
        Test the `is_connection_operational` method with various scenarios.

        This test verifies that the method correctly determines Redis readiness
        based on the connection state, `ping` result, and exceptions using a
        parameterized table-driven approach.
        """

        # Given:
        # Create a new redis instance.
        redis = get_redis_connection()
        # Replace the connection with prepared fixtures.
        redis.connection = connection

        # When:
        result = redis.is_connection_operational()

        # Then:
        assert result == expected, f"Failed test case: {test_case}"

        # Clean up by resetting the Redis instance.
        redis.reset()

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

        This test verifies that the method correctly determines if a connection
        exists based on the connection state using a parameterized table-driven approach.
        """

        # Given:
        # Create a new redis instance.
        redis = get_redis_connection()
        # Replace the connection with prepared fixtures.
        redis.connection = connection

        # When:
        result = redis.has_connection()

        # Then:
        assert result == expected, f"Failed test case: {test_case}"

        # Clean up by resetting the Redis instance.
        redis.reset()

    def test_reset(self):
        """
        Test the `reset` method of the Redis class.

        This test verifies that the reset method clears the singleton instance
        and any associated resources.
        """

        # Given:
        # Create a new redis instance.
        redis = get_redis_connection()

        # When:
        redis.reset()
        redis2 = get_redis_connection()

        # Then:
        assert redis != redis2

