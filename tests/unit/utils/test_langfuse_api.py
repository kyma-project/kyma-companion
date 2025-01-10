import pytest
from unittest.mock import patch, Mock
from requests.exceptions import HTTPError

from agents.common.constants import SUCCESS_CODE
from utils.common import MetricsResponse
from utils.langfuse import LangfuseAPI

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


# Mock response for successful API call
mock_success_response = Mock()
mock_success_response.status_code = SUCCESS_CODE
mock_success_response.json.return_value = mock_metrics_data

# Mock response for failed API call
mock_failed_response = Mock()
mock_failed_response.status_code = 404
mock_failed_response.raise_for_status.side_effect = HTTPError("Not Found")

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
        # Test case 4: Failed API call
        (
            "2025-01-08T13:50:56.406Z",
            "2025-12-16T13:50:56.406Z",
            None,
            None,
            None,
        ),
    ],
)
def test_get_daily_metrics(from_timestamp, to_timestamp, tags, user_id, expected_result):
    with patch("requests.get") as mock_get:
        if expected_result:
            mock_get.return_value = mock_success_response
        else:
            mock_get.return_value = mock_failed_response

        api = LangfuseAPI()
        if expected_result:
            result = api.get_daily_metrics(from_timestamp, to_timestamp, tags, user_id)
            assert result == expected_result
        else:
            with pytest.raises(HTTPError):
                api.get_daily_metrics(from_timestamp, to_timestamp, tags, user_id)

@pytest.mark.parametrize(
    "from_timestamp, to_timestamp, tags, expected_total_usage",
    [
        # Test case 1: Successful call with no tags
        (
            "2025-01-08T13:50:56.406Z",
            "2025-12-16T13:50:56.406Z",
            None,
            1050,  # 300 + 150 + 400 + 200
        ),
        # Test case 2: Successful call with tags
        (
            "2025-01-08T13:50:56.406Z",
            "2025-12-16T13:50:56.406Z",
            ["tag1"],
            1050,
        ),
        # Test case 3: Failed API call
        (
            "2025-01-08T13:50:56.406Z",
            "2025-12-16T13:50:56.406Z",
            None,
            0,
        ),
    ],
)
def test_get_total_token_usage(from_timestamp, to_timestamp, tags, expected_total_usage):
    with patch("requests.get") as mock_get:
        if expected_total_usage > 0:
            mock_get.return_value = mock_success_response
        else:
            mock_get.return_value = mock_failed_response

        api = LangfuseAPI()
        if expected_total_usage > 0:
            result = api.get_total_token_usage(from_timestamp, to_timestamp, tags)
            assert result == expected_total_usage
        else:
            with pytest.raises(HTTPError):
                api.get_total_token_usage(from_timestamp, to_timestamp, tags)