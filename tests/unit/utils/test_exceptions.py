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
            # No message field - should return original
            (
                '{"error": "Something went wrong", "code": 500}',
                '{"error": "Something went wrong", "code": 500}',
            ),
            # Invalid JSON
            ("This is not a JSON string", "This is not a JSON string"),
            # Empty string
            ("", ""),
            # Malformed JSON
            ('{"message": "incomplete json', '{"message": "incomplete json'),
            # JSON array
            ('["error1", "error2"]', '["error1", "error2"]'),
        ],
    )
    def test_parse_k8s_error_response(self, error_text, expected_result):
        """Test parsing K8s error responses with various input formats."""
        result = parse_k8s_error_response(error_text)
        assert result == expected_result


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
        "exception_type,exception_data,tool_name,uri,expected_status,expected_message_check",
        [
            # K8sClientError with new URI
            (
                "k8s_client_error",
                {
                    "message": "Original error",
                    "status_code": HTTPStatus.BAD_REQUEST,
                    "uri": "/original/uri",
                    "tool_name": "original_tool",
                },
                "new_tool",
                "/new/uri",
                HTTPStatus.BAD_REQUEST,
                lambda msg: msg == "Original error",
            ),
            # K8sClientError preserving original URI
            (
                "k8s_client_error",
                {
                    "message": "Original error",
                    "status_code": HTTPStatus.BAD_REQUEST,
                    "uri": "/original/uri",
                    "tool_name": "original_tool",
                },
                "new_tool",
                "",
                HTTPStatus.BAD_REQUEST,
                lambda msg: msg == "Original error",
            ),
            # ApiException with valid status
            (
                "api_exception",
                {
                    "status": HTTPStatus.NOT_FOUND,
                    "has_http_resp": True,
                    "error_msg": "Pod not found",
                },
                "get_pod",
                "/api/v1/pods/test",
                HTTPStatus.NOT_FOUND,
                lambda msg: "Pod not found" in msg,
            ),
            # ApiException with invalid status - non-numeric
            (
                "api_exception",
                {"status": "invalid", "has_http_resp": True, "error_msg": "Error"},
                "test_tool",
                "",
                HTTPStatus.INTERNAL_SERVER_ERROR,
                lambda msg: "Error" in msg,
            ),
            # ApiException with out of range status
            (
                "api_exception",
                {"status": 999, "has_http_resp": True, "error_msg": "Error"},
                "test_tool",
                "",
                HTTPStatus.INTERNAL_SERVER_ERROR,
                lambda msg: "Error" in msg,
            ),
            # ApiException below minimum range
            (
                "api_exception",
                {"status": 99, "has_http_resp": True, "error_msg": "Error"},
                "test_tool",
                "",
                HTTPStatus.INTERNAL_SERVER_ERROR,
                lambda msg: "Error" in msg,
            ),
            # ApiException above maximum range
            (
                "api_exception",
                {"status": 600, "has_http_resp": True, "error_msg": "Error"},
                "test_tool",
                "",
                HTTPStatus.INTERNAL_SERVER_ERROR,
                lambda msg: "Error" in msg,
            ),
            # ApiException without http_resp
            (
                "api_exception",
                {
                    "status": HTTPStatus.NOT_FOUND,
                    "has_http_resp": False,
                    "error_msg": "Error",
                },
                "test_tool",
                "",
                HTTPStatus.INTERNAL_SERVER_ERROR,
                lambda msg: "Error" in msg,
            ),
            # ApiException with boundary status codes
            (
                "api_exception",
                {
                    "status": HTTPStatus.CONTINUE,
                    "has_http_resp": True,
                    "error_msg": "Error",
                },
                "test_tool",
                "",
                HTTPStatus.CONTINUE,
                lambda msg: "Error" in msg,
            ),
            (
                "api_exception",
                {"status": 599, "has_http_resp": True, "error_msg": "Error"},
                "test_tool",
                "",
                599,
                lambda msg: "Error" in msg,
            ),
            (
                "api_exception",
                {"status": HTTPStatus.OK, "has_http_resp": True, "error_msg": "Error"},
                "test_tool",
                "",
                HTTPStatus.OK,
                lambda msg: "Error" in msg,
            ),
            # Generic exception
            (
                "generic",
                {"error_msg": "Invalid value"},
                "validate_input",
                "/api/validate",
                HTTPStatus.INTERNAL_SERVER_ERROR,
                lambda msg: msg == "Invalid value",
            ),
            # Non-ApiException with status attribute (should be ignored)
            (
                "custom_exception",
                {"status": HTTPStatus.FORBIDDEN, "error_msg": "Custom error"},
                "test_tool",
                "",
                HTTPStatus.INTERNAL_SERVER_ERROR,
                lambda msg: "Custom error" in msg,
            ),
        ],
    )
    def test_from_exception(
        self,
        exception_type,
        exception_data,
        tool_name,
        uri,
        expected_status,
        expected_message_check,
    ):
        """Test from_exception method with various exception types and scenarios."""
        # Create the exception based on type
        if exception_type == "k8s_client_error":
            exception = K8sClientError(**exception_data)
        elif exception_type == "api_exception":
            mock_exception = MagicMock()
            mock_exception.__class__.__name__ = "ApiException"
            mock_exception.status = exception_data["status"]
            if exception_data["has_http_resp"]:
                mock_exception.http_resp = MagicMock()
            else:
                delattr(mock_exception, "http_resp")
            mock_exception.__str__ = MagicMock(return_value=exception_data["error_msg"])
            exception = mock_exception
        elif exception_type == "generic":
            exception = ValueError(exception_data["error_msg"])
        elif exception_type == "custom_exception":
            mock_exception = MagicMock()
            mock_exception.__class__.__name__ = "CustomException"
            mock_exception.status = exception_data["status"]
            mock_exception.__str__ = MagicMock(return_value=exception_data["error_msg"])
            exception = mock_exception

        # Call from_exception
        kwargs = {"exception": exception, "tool_name": tool_name}
        if uri:
            kwargs["uri"] = uri

        error = K8sClientError.from_exception(**kwargs)

        # Assertions
        assert error.status_code == expected_status
        assert expected_message_check(error.message)
        assert error.tool_name == tool_name
