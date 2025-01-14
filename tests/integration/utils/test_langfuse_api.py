import pytest
import os
from aiohttp import ClientSession, BasicAuth
from datetime import datetime, timedelta
from datetime import UTC, datetime

from agents.common.utils import get_current_day_timestamps_utc
from utils.common import MetricsResponse
from utils.langfuse import LangfuseService


@pytest.fixture
def langfuse_service():
    return LangfuseService()

@pytest.mark.asyncio
async def test_get_daily_metrics(langfuse_service):
    # Define the timestamps for the test
    to_timestamp,from_timestamp = get_current_day_timestamps_utc()

    # Call the method to test
    response = await langfuse_service.get_daily_metrics(from_timestamp, to_timestamp)

    # Assert that the response is not None and is of the correct type
    assert response is not None
    assert isinstance(response, MetricsResponse)

    # Optionally, you can add more assertions to validate the structure of the response
    if response.data:
        for daily_metric in response.data:
            assert hasattr(daily_metric, 'date')
            assert hasattr(daily_metric, 'usage')
            for usage in daily_metric.usage:
                assert hasattr(usage, 'total_usage')

@pytest.mark.asyncio
async def test_get_total_token_usage(langfuse_service):
    # Define the timestamps for the test
    to_timestamp,from_timestamp = get_current_day_timestamps_utc()

    total_token_usage = await langfuse_service.get_total_token_usage(from_timestamp, to_timestamp)

    # Assert that the total token usage is an integer
    assert isinstance(total_token_usage, int)
    assert total_token_usage >= 0
