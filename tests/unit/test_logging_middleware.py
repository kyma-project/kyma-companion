import logging
from http import HTTPStatus
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import Response

from main import logging_middleware


@pytest.fixture
def mock_request():
    """Create a mock request with configurable properties."""
    request = Mock()
    request.method = "GET"
    request.url = Mock()
    request.url.path = "/api/test"
    request.client = Mock()
    request.client.host = "127.0.0.1"
    return request


@pytest.fixture
def mock_call_next():
    """Create a mock call_next that returns a successful response."""

    async def _call_next(request):
        response = Response(status_code=HTTPStatus.OK)
        return response

    return _call_next


@pytest.mark.asyncio
class TestLoggingMiddleware:
    """Tests for logging_middleware function."""

    async def test_logs_regular_request_at_info_level(self, mock_request, mock_call_next):
        """Test that regular requests are logged at INFO level."""
        mock_request.url.path = "/api/users"

        with patch("main.access_logger") as mock_logger:
            response = await logging_middleware(mock_request, mock_call_next)

            assert response.status_code == HTTPStatus.OK
            mock_logger.log.assert_called_once()

            # Verify INFO level was used
            call_args = mock_logger.log.call_args
            assert call_args[0][0] == logging.INFO

    async def test_logs_healthz_200_at_debug_level(self, mock_request, mock_call_next):
        """Test that successful /healthz requests are logged at DEBUG level."""
        mock_request.url.path = "/healthz"

        with patch("main.access_logger") as mock_logger:
            response = await logging_middleware(mock_request, mock_call_next)

            assert response.status_code == HTTPStatus.OK
            mock_logger.log.assert_called_once()

            # Verify DEBUG level was used
            call_args = mock_logger.log.call_args
            assert call_args[0][0] == logging.DEBUG

    async def test_logs_readyz_200_at_debug_level(self, mock_request, mock_call_next):
        """Test that successful /readyz requests are logged at DEBUG level."""
        mock_request.url.path = "/readyz"

        with patch("main.access_logger") as mock_logger:
            response = await logging_middleware(mock_request, mock_call_next)

            assert response.status_code == HTTPStatus.OK
            mock_logger.log.assert_called_once()

            # Verify DEBUG level was used
            call_args = mock_logger.log.call_args
            assert call_args[0][0] == logging.DEBUG

    async def test_logs_healthz_non_200_at_warning_level(self, mock_request):
        """Test that failed /healthz requests are logged at WARNING level."""
        mock_request.url.path = "/healthz"

        async def failing_call_next(request):
            return Response(status_code=HTTPStatus.SERVICE_UNAVAILABLE)

        with patch("main.access_logger") as mock_logger:
            response = await logging_middleware(mock_request, failing_call_next)

            assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
            mock_logger.log.assert_called_once()

            # Verify WARNING level was used
            call_args = mock_logger.log.call_args
            assert call_args[0][0] == logging.WARNING

    async def test_logs_readyz_non_200_at_warning_level(self, mock_request):
        """Test that failed /readyz requests are logged at WARNING level."""
        mock_request.url.path = "/readyz"

        async def failing_call_next(request):
            return Response(status_code=HTTPStatus.INTERNAL_SERVER_ERROR)

        with patch("main.access_logger") as mock_logger:
            response = await logging_middleware(mock_request, failing_call_next)

            assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
            mock_logger.log.assert_called_once()

            # Verify WARNING level was used
            call_args = mock_logger.log.call_args
            assert call_args[0][0] == logging.WARNING

    async def test_includes_structured_logging_fields(self, mock_request, mock_call_next):
        """Test that all structured logging fields are included."""
        mock_request.method = "POST"
        mock_request.url.path = "/api/create"
        mock_request.client.host = "192.168.1.100"

        with patch("main.access_logger") as mock_logger:
            response = await logging_middleware(mock_request, mock_call_next)

            call_args = mock_logger.log.call_args
            extra_fields = call_args[1]["extra"]

            assert extra_fields["method"] == "POST"
            assert extra_fields["path"] == "/api/create"
            assert extra_fields["status_code"] == HTTPStatus.OK
            assert extra_fields["client"] == "192.168.1.100"
            assert "duration_ms" in extra_fields
            assert isinstance(extra_fields["duration_ms"], float)

    async def test_handles_missing_client_gracefully(self, mock_request, mock_call_next):
        """Test that middleware handles missing client information."""
        mock_request.client = None

        with patch("main.access_logger") as mock_logger:
            response = await logging_middleware(mock_request, mock_call_next)

            assert response.status_code == HTTPStatus.OK
            call_args = mock_logger.log.call_args
            extra_fields = call_args[1]["extra"]

            assert extra_fields["client"] == "unknown"

    async def test_measures_request_duration(self, mock_request):
        """Test that request duration is measured and included."""
        import asyncio

        async def slow_call_next(request):
            await asyncio.sleep(0.01)  # 10ms delay
            return Response(status_code=HTTPStatus.OK)

        with patch("main.access_logger") as mock_logger:
            response = await logging_middleware(mock_request, slow_call_next)

            call_args = mock_logger.log.call_args
            extra_fields = call_args[1]["extra"]

            # Duration should be at least 10ms (accounting for overhead)
            assert extra_fields["duration_ms"] >= 10.0

    async def test_log_message_format(self, mock_request, mock_call_next):
        """Test that log message has correct format."""
        mock_request.method = "DELETE"
        mock_request.url.path = "/api/resource/123"
        mock_request.client.host = "10.0.0.5"

        with patch("main.access_logger") as mock_logger:
            response = await logging_middleware(mock_request, mock_call_next)

            call_args = mock_logger.log.call_args
            log_message = call_args[0][1]

            expected_message = f'10.0.0.5 - "DELETE /api/resource/123" {HTTPStatus.OK}'
            assert log_message == expected_message

    @pytest.mark.parametrize(
        "status_code",
        [
            HTTPStatus.CREATED,
            HTTPStatus.ACCEPTED,
            HTTPStatus.NO_CONTENT,
            HTTPStatus.BAD_REQUEST,
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
            HTTPStatus.NOT_FOUND,
            HTTPStatus.INTERNAL_SERVER_ERROR,
        ],
    )
    async def test_handles_various_status_codes(self, mock_request, status_code):
        """Test that middleware correctly handles various HTTP status codes."""

        async def custom_call_next(request):
            return Response(status_code=status_code)

        with patch("main.access_logger") as mock_logger:
            response = await logging_middleware(mock_request, custom_call_next)

            assert response.status_code == status_code
            call_args = mock_logger.log.call_args
            extra_fields = call_args[1]["extra"]

            assert extra_fields["status_code"] == status_code

    async def test_duration_rounded_to_two_decimals(self, mock_request, mock_call_next):
        """Test that duration is rounded to 2 decimal places."""
        with patch("main.access_logger") as mock_logger:
            response = await logging_middleware(mock_request, mock_call_next)

            call_args = mock_logger.log.call_args
            extra_fields = call_args[1]["extra"]
            duration_str = str(extra_fields["duration_ms"])

            # Check that duration has at most 2 decimal places
            if "." in duration_str:
                decimal_places = len(duration_str.split(".")[1])
                assert decimal_places <= 2
