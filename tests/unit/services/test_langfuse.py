from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import ClientResponseError
from aiohttp.web_exceptions import HTTPError

from agents.common.constants import SUCCESS_CODE
from services.langfuse import LangfuseService
from utils.common import MetricsResponse

ERROR_STATUS_CODE = 500
TOKEN_LIMIT_PER_CLUSTER = 1000

# Mock data for MetricsResponse
mock_metrics_data = {
    "data": [
        {
            "date": "2025-01-08",
            "countTraces": 10,
            "countObservations": 20,
            "totalCost": 50.0,
            "usage": [
                {
                    "model": "gpt-4",
                    "inputUsage": 100,
                    "outputUsage": 200,
                    "totalUsage": 300,
                    "totalCost": 30.0,
                    "countObservations": 10,
                    "countTraces": 5,
                },
                {
                    "model": "gpt-3.5",
                    "inputUsage": 50,
                    "outputUsage": 100,
                    "totalUsage": 150,
                    "totalCost": 20.0,
                    "countObservations": 10,
                    "countTraces": 5,
                },
            ],
        },
        {
            "date": "2025-01-09",
            "countTraces": 15,
            "countObservations": 25,
            "totalCost": 60.0,
            "usage": [
                {
                    "model": "gpt-4",
                    "inputUsage": 150,
                    "outputUsage": 250,
                    "totalUsage": 400,
                    "totalCost": 40.0,
                    "countObservations": 15,
                    "countTraces": 10,
                },
                {
                    "model": "gpt-3.5",
                    "inputUsage": 75,
                    "outputUsage": 125,
                    "totalUsage": 200,
                    "totalCost": 20.0,
                    "countObservations": 10,
                    "countTraces": 5,
                },
            ],
        },
    ],
    "meta": {
        "page": 1,
        "limit": 10,
        "totalItems": 2,
        "totalPages": 1,
    },
}


@pytest.mark.parametrize(
    "from_timestamp, to_timestamp, tags, user_id, expected_result",
    [
        # Test case 1: Successful call with no tags or user_id
        (
            "2025-01-08T13:50:56.406Z",
            "2025-12-16T13:50:56.406Z",
            None,
            None,
            MetricsResponse(**mock_metrics_data),
        ),
        # Test case 2: Successful call with tags
        (
            "2025-01-08T13:50:56.406Z",
            "2025-12-16T13:50:56.406Z",
            ["tag1"],
            None,
            MetricsResponse(**mock_metrics_data),
        ),
        # Test case 3: Successful call with user_id
        (
            "2025-01-08T13:50:56.406Z",
            "2025-12-16T13:50:56.406Z",
            None,
            "user123",
            MetricsResponse(**mock_metrics_data),
        ),
    ],
)
@pytest.mark.asyncio
async def test_get_daily_metrics(
    from_timestamp, to_timestamp, tags, user_id, expected_result
):
    """
    Test the `get_daily_metrics` method of the LangfuseService class.

    This test verifies that the method correctly handles successful API responses
    and raises appropriate exceptions for failed responses. It tests three scenarios:
    1. A successful call with no tags or user_id.
    2. A successful call with tags.
    3. A successful call with a user_id.

    """
    with patch("aiohttp.ClientSession.get") as mock_get:
        if expected_result:
            # Mock successful response
            mock_response = AsyncMock()
            mock_response.status = SUCCESS_CODE
            mock_response.json.return_value = mock_metrics_data
            mock_get.return_value.__aenter__.return_value = mock_response
        else:
            # Mock failed response
            mock_response = AsyncMock()
            mock_response.status = ERROR_STATUS_CODE
            mock_response.raise_for_status.side_effect = ClientResponseError(
                request_info=None,
                history=None,
                status=ERROR_STATUS_CODE,
                message="Not Found",
            )
            mock_get.return_value.__aenter__.return_value = mock_response

        api = LangfuseService()
        if expected_result:
            result = await api.get_daily_metrics(
                from_timestamp, to_timestamp, tags, user_id
            )
            assert result == expected_result
        else:
            with pytest.raises(Exception) as exc_info:
                await api.get_daily_metrics(from_timestamp, to_timestamp, tags, user_id)
            assert exc_info.value.status == ERROR_STATUS_CODE


def _raise_exception(*args):
    raise HTTPError()


@pytest.mark.asyncio
async def test_get_daily_metrics_failure():
    """This test verifies that the method raises an HTTPError when the API call fails."""
    with patch("aiohttp.ClientSession.get") as mock_get:
        # Mock failed response
        mock_response = AsyncMock()

        # Set attributes required by the real raise_for_status method
        mock_response.status = ERROR_STATUS_CODE
        mock_response.raise_for_status = _raise_exception

        # Ensure the mock_get returns the mock_response
        mock_get.return_value.__aenter__.return_value = mock_response
        api = LangfuseService()

        # Ensure the error is raised
        with pytest.raises(HTTPError):
            await api.get_daily_metrics(
                "2025-01-08T13:50:56.406Z", "2025-12-16T13:50:56.406Z"
            )


@pytest.mark.parametrize(
    "from_timestamp, to_timestamp, tags, expected_total_usage",
    [
        # Test case 1: Successful call with no tags
        (
            "2025-01-08T13:50:56.406Z",
            "2025-12-16T13:50:56.406Z",
            None,
            1050,
        ),
        # Test case 2: Successful call with tags
        (
            "2025-01-08T13:50:56.406Z",
            "2025-12-16T13:50:56.406Z",
            ["tag1"],
            1050,
        ),
    ],
)
@pytest.mark.asyncio
async def test_get_total_token_usage(
    from_timestamp, to_timestamp, tags, expected_total_usage
):
    """
    This test verifies that the method correctly calculates the total token usage
    based on the provided timestamps and optional tags. It tests two scenarios:
    1. A successful call with no tags.
    2. A successful call with tags.
    """
    with patch("aiohttp.ClientSession.get") as mock_get:
        if expected_total_usage > 0:
            # Mock successful response
            mock_response = AsyncMock()
            mock_response.status = SUCCESS_CODE
            mock_response.json.return_value = mock_metrics_data
            mock_get.return_value.__aenter__.return_value = mock_response
        else:
            # Mock failed response
            mock_response = AsyncMock()
            mock_response.status = ERROR_STATUS_CODE
            mock_response.raise_for_status.side_effect = ClientResponseError(
                request_info=None, history=None, status=ERROR_STATUS_CODE
            )
            mock_get.return_value.__aenter__.return_value = mock_response

        api = LangfuseService()
        result = await api.get_total_token_usage(from_timestamp, to_timestamp, tags)
        if expected_total_usage > 0:

            assert result == expected_total_usage
        else:
            with pytest.raises(ClientResponseError):
                await api.get_total_token_usage(from_timestamp, to_timestamp, tags)
