import json
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic_core import ValidationError

from agents.common.constants import ERROR_RATE_LIMIT_CODE
from main import handle_http_exception


@pytest.fixture
def mock_request():
    """Create a mock request object."""
    return MagicMock(spec=Request)


@pytest.fixture
def mock_call_next():
    """Create a mock call_next function."""
    return AsyncMock()


@pytest.mark.parametrize(
    "status_code,expected_error,expected_message",
    [
        (HTTPStatus.UNAUTHORIZED, "Unauthorized", "Authentication failed"),
        (HTTPStatus.FORBIDDEN, "Unauthorized", "Authentication failed"),
        (HTTPStatus.NOT_FOUND, "Not Found", "Requested resource not found"),
        (HTTPStatus.BAD_REQUEST, "Bad Request", "Invalid request format or parameters"),
        (
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "Validation Error",
            "Request validation failed",
        ),
        (
            HTTPStatus.METHOD_NOT_ALLOWED,
            "Method Not Allowed",
            "HTTP method not supported for this endpoint",
        ),
        (
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "Internal Server Error",
            "Something went wrong.",
        ),
        (
            HTTPStatus.REQUEST_TIMEOUT,
            "Request Timeout",
            "Request took too long to process",
        ),
        # Not implemented status code should give generic output
        (
            HTTPStatus.CONFLICT,
            "Request Error",
            "An error occurred, Please try again later.",
        ),
        (
            HTTPStatus.REQUEST_URI_TOO_LONG,
            "Request Error",
            "An error occurred, Please try again later.",
        ),
        (
            HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            "Request Error",
            "An error occurred, Please try again later.",
        ),
    ],
)
@pytest.mark.asyncio
async def test_http_exception_handling(
    mock_request,
    mock_call_next,
    status_code,
    expected_error,
    expected_message,
):
    """Test handling of various HTTP exceptions."""

    http_exc = HTTPException(status_code=status_code, detail="Test error")

    response = handle_http_exception(http_exc)

    assert isinstance(response, JSONResponse)
    assert response.status_code == status_code

    content = json.loads(response.body.decode())
    assert content["error"] == expected_error
    assert content["message"] == expected_message


@pytest.mark.asyncio
async def test_rate_limit_exception_handling(mock_request, mock_call_next):
    """Test handling of rate limit exceptions."""
    retry_after_sec = 542523
    rate_limit_detail = {
        "error": "Token usage limit exceeded",
        "message": "Token usage limit of 5000000 exceeded for this cluster. "
        "To ensure a fair usage, Kyma Companion controls the number"
        " of requests a cluster can make within 24 hours.",
        "current_usage": 6000000,
        "limit": 5000000,
        "time_remaining_seconds": retry_after_sec,
    }
    rate_limit_headers = {"Retry-After": str(retry_after_sec)}
    http_exc = HTTPException(
        status_code=ERROR_RATE_LIMIT_CODE,
        detail=rate_limit_detail,
        headers=rate_limit_headers,
    )

    response = handle_http_exception(http_exc)

    assert isinstance(response, JSONResponse)
    assert response.status_code == ERROR_RATE_LIMIT_CODE

    content = json.loads(response.body.decode())
    assert content == rate_limit_detail
    assert response.headers["Retry-After"] == str(retry_after_sec)


@pytest.mark.asyncio
async def test_request_validation_error_with_bytes_input(mock_request, mock_call_next):
    """Test that RequestValidationError with bytes input is properly serialized.

    This test ensures that validation errors containing bytes (e.g., from invalid
    JSON requests) are properly converted to JSON-serializable strings using
    FastAPI's jsonable_encoder, preventing JSON serialization errors.

    This addresses an issue that appeared when upgrading to FastAPI 0.133.x where
    validation errors include the raw request body as bytes.
    """
    # Create a validation error that mimics what Pydantic returns when
    # receiving invalid JSON with bytes in the input field
    validation_error = ValidationError.from_exception_data(
        "RequestValidationError",
        [
            {
                "type": "json_invalid",
                "loc": ("body",),
                "msg": "JSON decode error",
                "input": b"invalid json",  # bytes input that needs conversion
                "ctx": {"error": "Expecting value"},
            }
        ],
    )

    request_validation_error = RequestValidationError(errors=validation_error.errors())

    response = handle_http_exception(request_validation_error)

    assert isinstance(response, JSONResponse)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    # Verify the response can be successfully serialized to JSON
    content = json.loads(response.body.decode())

    # Verify structure matches expected validation error format
    assert "error" in content
    assert "message" in content
    assert "detail" in content
    assert content["error"] == "Validation Error"
    assert content["message"] == "Request validation failed"

    # Verify the error details are present and serializable
    assert isinstance(content["detail"], list)
    assert len(content["detail"]) > 0

    # Verify bytes have been converted to string
    error_detail = content["detail"][0]
    assert "input" in error_detail
    assert isinstance(error_detail["input"], str)  # Should be string, not bytes
    assert error_detail["input"] == "invalid json"
