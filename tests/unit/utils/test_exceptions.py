from http import HTTPStatus
from unittest.mock import MagicMock

import pytest

from utils.exceptions import K8sClientError, parse_k8s_error_response


class TestParseK8sErrorResponse:
    """Test cases for parse_k8s_error_response function."""

    @pytest.mark.parametrize(
        "error_text,expected_result",
        [
            # Valid JSON with message field
            ('{"message": "Pod not found", "code": 404}', "Pod not found"),
            # Valid JSON with None message
            ('{"message": null, "code": 404}', "None"),
            # Empty string message
            ('{"message": "", "code": 400}', ""),
            # Numeric message
            ('{"message": 12345, "code": 500}', "12345"),
            # Boolean message
            ('{"message": true, "code": 500}', "True"),
            # Object message
            ('{"message": {"detail": "error"}, "code": 500}', "{'detail': 'error'}"),
            # Nested JSON structure
            (
                '{"status": "Failure", "message": "namespace not found", "details": {"name": "test"}}',
                "namespace not found",
            ),
            # Special characters
            (
                '{"message": "Error: \\n\\t\'quotes\' and \\"double quotes\\""}',
                "Error: \n\t'quotes' and \"double quotes\"",
            ),
            # Unicode characters and emojis
            (
                '{"message": "Error: Resource not found 🔍"}',
                "Error: Resource not found 🔍",
            ),
        ],
    )
    def test_valid_json_with_message(self, error_text, expected_result):
        """Test parsing valid JSON with various message types."""
        result = parse_k8s_error_response(error_text)
        assert result == expected_result

    @pytest.mark.parametrize(
        "error_text",
        [
            '{"error": "Something went wrong", "code": 500}',  # No message field
            "This is not a JSON string",  # Invalid JSON
            "",  # Empty string
            '{"message": "incomplete json',  # Malformed JSON
            '["error1", "error2"]',  # JSON array
        ],
    )
    def test_invalid_or_missing_message_returns_original(self, error_text):
        """Test that invalid JSON or missing message returns the original text."""
        result = parse_k8s_error_response(error_text)
        assert result == error_text


class TestK8sClientError:
    """Test cases for K8sClientError class."""

    @pytest.mark.parametrize(
        "message,status_code,uri,tool_name,expected_status,expected_uri,expected_tool",
        [
            # All parameters provided
            (
                "Test error",
                HTTPStatus.NOT_FOUND,
                "/api/v1/pods",
                "get_pod",
                HTTPStatus.NOT_FOUND,
                "/api/v1/pods",
                "get_pod",
            ),
            # Only message (defaults)
            (
                "Test error",
                None,
                None,
                None,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "",
                "",
            ),
        ],
    )
    def test_init(
        self,
        message,
        status_code,
        uri,
        tool_name,
        expected_status,
        expected_uri,
        expected_tool,
    ):
        """Test K8sClientError initialization with various parameters."""
        kwargs = {"message": message}
        if status_code is not None:
            kwargs["status_code"] = status_code
        if uri is not None:
            kwargs["uri"] = uri
        if tool_name is not None:
            kwargs["tool_name"] = tool_name

        error = K8sClientError(**kwargs)
        assert error.message == message
        assert error.status_code == expected_status
        assert error.uri == expected_uri
        assert error.tool_name == expected_tool

    @pytest.mark.parametrize(
        "message,tool_name,uri,expected",
        [
            # Both tool_name and uri
            (
                "Resource not found",
                "get_resource",
                "/api/v1/pods/test",
                "failed executing get_resource with URI: /api/v1/pods/test,"
                "raised the following error: Resource not found",
            ),
            # Only tool_name
            (
                "Connection timeout",
                "list_pods",
                "",
                "failed executing list_pods, raised the following error: Connection timeout",
            ),
            # Only uri
            (
                "Invalid request",
                "",
                "/api/v1/namespaces/default/pods",
                "with URI: /api/v1/namespaces/default/pods, "
                "raised the following error: Invalid request",
            ),
            # Only message
            ("Generic error", "", "", "Generic error"),
        ],
    )
    def test_format_message(self, message, tool_name, uri, expected):
        """Test message formatting with various parameter combinations."""
        error = K8sClientError(message=message, tool_name=tool_name, uri=uri)
        assert str(error) == expected
        # Also verify __repr__ matches __str__ for LangChain compatibility
        assert repr(error) == str(error)

    @pytest.mark.parametrize(
        "new_uri,expected_uri",
        [
            ("/new/uri", "/new/uri"),  # URI is updated
            ("", "/original/uri"),  # Original URI preserved
        ],
    )
    def test_from_exception_with_k8s_client_error(self, new_uri, expected_uri):
        """Test from_exception preserves K8sClientError properties."""
        original_error = K8sClientError(
            message="Original error",
            status_code=HTTPStatus.BAD_REQUEST,
            uri="/original/uri",
            tool_name="original_tool",
        )
        kwargs = {"exception": original_error, "tool_name": "new_tool"}
        if new_uri:
            kwargs["uri"] = new_uri

        new_error = K8sClientError.from_exception(**kwargs)
        assert new_error.message == "Original error"
        assert new_error.status_code == HTTPStatus.BAD_REQUEST
        assert new_error.uri == expected_uri
        assert new_error.tool_name == "new_tool"

    def test_from_exception_with_api_exception(self):
        """Test from_exception extracts status from Kubernetes ApiException."""
        # Create a mock ApiException
        mock_exception = MagicMock()
        mock_exception.__class__.__name__ = "ApiException"
        mock_exception.status = HTTPStatus.NOT_FOUND
        mock_exception.http_resp = MagicMock()  # Simulate HTTP response
        mock_exception.__str__ = MagicMock(return_value="Pod not found")

        error = K8sClientError.from_exception(
            exception=mock_exception,
            tool_name="get_pod",
            uri="/api/v1/pods/test",
        )
        assert error.status_code == HTTPStatus.NOT_FOUND
        assert "Pod not found" in error.message

    @pytest.mark.parametrize(
        "status_value,description",
        [
            ("invalid", "non-numeric status"),
            (999, "out of valid range"),
            (99, "below minimum range"),
            (600, "above maximum range"),
        ],
    )
    def test_from_exception_with_api_exception_invalid_status(
        self, status_value, description
    ):
        """Test from_exception handles invalid status codes from ApiException."""
        mock_exception = MagicMock()
        mock_exception.__class__.__name__ = "ApiException"
        mock_exception.status = status_value
        mock_exception.http_resp = MagicMock()
        mock_exception.__str__ = MagicMock(return_value="Error")

        error = K8sClientError.from_exception(
            exception=mock_exception, tool_name="test_tool"
        )
        assert error.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    def test_from_exception_with_api_exception_no_http_resp(self):
        """Test from_exception requires http_resp attribute for ApiException."""
        mock_exception = MagicMock()
        mock_exception.__class__.__name__ = "ApiException"
        mock_exception.status = HTTPStatus.NOT_FOUND
        # No http_resp attribute
        delattr(mock_exception, "http_resp")
        mock_exception.__str__ = MagicMock(return_value="Error")

        error = K8sClientError.from_exception(
            exception=mock_exception, tool_name="test_tool"
        )
        # Should default to 500 since http_resp is missing
        assert error.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    def test_from_exception_with_generic_exception(self):
        """Test from_exception with generic exceptions defaults to 500 status."""
        exception = ValueError("Invalid value")
        error = K8sClientError.from_exception(
            exception=exception,
            tool_name="validate_input",
            uri="/api/validate",
        )
        assert error.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
        assert error.message == "Invalid value"
        assert error.tool_name == "validate_input"
        assert error.uri == "/api/validate"

    def test_from_exception_ignores_non_api_exception_status(self):
        """Test that non-ApiException status attributes are ignored."""
        mock_exception = MagicMock()
        mock_exception.__class__.__name__ = "CustomException"
        mock_exception.status = HTTPStatus.FORBIDDEN
        mock_exception.__str__ = MagicMock(return_value="Custom error")

        error = K8sClientError.from_exception(
            exception=mock_exception, tool_name="test_tool"
        )
        assert error.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    @pytest.mark.parametrize(
        "status_code,expected_code",
        [
            (HTTPStatus.CONTINUE, HTTPStatus.CONTINUE),  # Valid minimum (100)
            (599, 599),  # Valid maximum (non-standard, keep as int)
            (HTTPStatus.OK, HTTPStatus.OK),  # Common success (200)
            (HTTPStatus.NOT_FOUND, HTTPStatus.NOT_FOUND),  # Common error (404)
            (
                HTTPStatus.INTERNAL_SERVER_ERROR,
                HTTPStatus.INTERNAL_SERVER_ERROR,
            ),  # Server error (500)
        ],
    )
    def test_status_code_validation_boundaries(self, status_code, expected_code):
        """Test status code validation at various boundaries."""
        mock_exception = MagicMock()
        mock_exception.__class__.__name__ = "ApiException"
        mock_exception.status = status_code
        mock_exception.http_resp = MagicMock()
        mock_exception.__str__ = MagicMock(return_value="Error")

        error = K8sClientError.from_exception(
            exception=mock_exception, tool_name="test_tool"
        )
        assert error.status_code == expected_code
