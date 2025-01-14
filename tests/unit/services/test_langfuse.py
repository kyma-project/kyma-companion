from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import ClientResponseError
from aiohttp.web_exceptions import HTTPError
from fastapi import HTTPException

from agents.common.constants import ERROR_RATE_LIMIT_CODE, SUCCESS_CODE
from agents.common.utils import get_current_day_timestamps_utc
from routers.conversations import check_token_usage
from services.langfuse import LangfuseService
from utils.common import MetricsResponse
from utils.settings import TOKEN_LIMIT_PER_CLUSTER

ERROR_STATUS_CODE = 500

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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "x_cluster_url, total_token_usage, expected_exception, expected_detail",
    [
        # Test case 1: Token usage is below the limit, no exception should be raised
        (
            "https://cluster1.example.com",
            500,
            None,
            None,
        ),
        # Test case 2: Token usage exceeds the limit, HTTPException should be raised
        (
            "https://cluster2.example.com",
            TOKEN_LIMIT_PER_CLUSTER + 100,
            HTTPException,
            {
                "error": "Rate limit exceeded",
                "message": f"Daily token limit of {TOKEN_LIMIT_PER_CLUSTER} exceeded for this cluster",
                "current_usage": TOKEN_LIMIT_PER_CLUSTER + 100,
                "limit": TOKEN_LIMIT_PER_CLUSTER,
                "time_remaining_seconds": 6399,  # just a random number
            },
        ),
        # Test case 3: Langfuse API fails, no exception should be raised
        (
            "https://cluster3.example.com",
            0,
            None,
            None,
        ),
    ],
)
async def test_check_token_usage(
    x_cluster_url, total_token_usage, expected_exception, expected_detail
):
    # Mock the Langfuse service
    langfuse_service = AsyncMock()

    # Mock the get_total_token_usage method
    if total_token_usage == 0:
        langfuse_service.get_total_token_usage.side_effect = Exception("API Error")
    else:
        langfuse_service.get_total_token_usage.return_value = total_token_usage

    # Mock the current time to control the time_remaining calculation
    current_utc = datetime.now(UTC)
    midnight_utc = current_utc.replace(hour=23, minute=59, second=59)
    time_remaining = midnight_utc - current_utc
    seconds_remaining = int(time_remaining.total_seconds())

    if expected_detail:
        expected_detail["time_remaining_seconds"] = seconds_remaining

    if expected_exception:
        with pytest.raises(expected_exception) as exc_info:
            await check_token_usage(x_cluster_url, langfuse_service)

        assert exc_info.value.status_code == ERROR_RATE_LIMIT_CODE
        assert exc_info.value.detail == expected_detail
        assert exc_info.value.headers == {"Retry-After": str(seconds_remaining)}
    else:
        await check_token_usage(x_cluster_url, langfuse_service)

    # Verify that the Langfuse service was called with the correct arguments
    from_timestamp, to_timestamp = get_current_day_timestamps_utc()
    cluster_id = x_cluster_url.split(".")[1]
    langfuse_service.get_total_token_usage.assert_called_once_with(
        from_timestamp, to_timestamp, cluster_id
    )
