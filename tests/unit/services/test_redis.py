from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.redis import Redis, get_redis


class TestRedis:
    @pytest.fixture(autouse=True)
    def mock_connection(self):
        with patch("services.redis.AsyncRedis") as mock:
            mock = MagicMock()
            yield mock

    @pytest.mark.parametrize(
        "test_case, connection_factory, expected",
        [
            ("No connection", None, False),
            (
                "Connection ready",
                MagicMock(return_value=MagicMock(ping=AsyncMock(return_value=True))),
                True,
            ),
            (
                "Connection not ready",
                MagicMock(return_value=MagicMock(ping=AsyncMock(return_value=False))),
                False,
            ),
            (
                "Connection fails with exception",
                MagicMock(
                    return_value=MagicMock(
                        ping=AsyncMock(side_effect=Exception("Connection error"))
                    )
                ),
                False,
            ),
            (
                "Connection Factory fails with exception",
                MagicMock(side_effect=Exception("Connection error")),
                False,
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_is_connection_operational(
        self, test_case, connection_factory, expected
    ):
        """
        Test the `is_connection_operational` method with various scenarios.

        This test verifies that the method correctly determines Redis readiness
        based on the connection state, `ping` result, and exceptions.
        """
        # When:
        redis = Redis(connection_factory)
        result = await redis.is_connection_operational()

        # Then:
        assert result == expected, f"Failed test case: {test_case}"

        # Clean up by resetting the instance.
        redis._reset_for_tests()

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
        redis = Redis(connection_factory)
        result = redis.has_connection()

        # Then:
        assert result == expected, f"Failed test case: {test_case}"

        # Clean up by resetting the instance.
        redis._reset_for_tests()

    def test_reset(self):
        """
        Test the `reset` method of the Redis class.

        This test verifies that the reset method clears the singleton instance
        and any associated resources.
        """

        # Given:
        # Create a new instance.
        redis1 = get_redis()

        # When:
        redis1._reset_for_tests()
        redis2 = get_redis()

        # Then:
        assert redis1 != redis2

        # Clean up by resetting the instance.
        redis2._reset_for_tests()
