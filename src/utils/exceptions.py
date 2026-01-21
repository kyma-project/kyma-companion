import json
from http import HTTPStatus

# HTTP status code validation range
# Covers standard codes (100-511) and common non-standard codes up to 599
_MIN_HTTP_STATUS_CODE = 100  # HTTPStatus.CONTINUE
_MAX_HTTP_STATUS_CODE = 599  # Extended range for non-standard codes


def parse_k8s_error_response(error_text: str) -> str:
    """
    Parse Kubernetes API error response and extract human-readable message.
    """
    try:
        error_json = json.loads(error_text)
        return str(error_json.get("message", error_text))
    except (json.JSONDecodeError, AttributeError, KeyError, TypeError):
        # If parsing fails for any reason, return the original text
        return error_text


class K8sClientError(Exception):
    """
    Custom exception for K8s client operations.

    This exception is used to wrap errors from Kubernetes operations,
    providing a unified error format with HTTP status codes and context.
    """

    def __init__(
        self,
        message: str,
        status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR,
        uri: str = "",
        tool_name: str = "",
    ):
        self.message = message
        self.status_code = status_code
        self.uri = uri
        self.tool_name = tool_name
        super().__init__(self._format_message())

    @classmethod
    def from_exception(
        cls,
        exception: Exception,
        tool_name: str,
        uri: str = "",
    ) -> "K8sClientError":
        """
        Create K8sClientError from an exception,
        extracting status code only from known Kubernetes exception types.

        Only Kubernetes ApiException status codes are extracted to ensure
        reliability and avoid misinterpreting custom exception status attributes.
        All other exceptions default to 500 Internal Server Error.
        """
        # If the exception is already a K8sClientError, preserve its status code and message
        if isinstance(exception, cls):
            return cls(
                message=exception.message,
                status_code=exception.status_code,
                uri=uri or exception.uri,
                tool_name=tool_name,
            )

        status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR

        # Only extract status from Kubernetes ApiException that comes from HTTP response
        if (
            hasattr(exception, "__class__")
            and exception.__class__.__name__ == "ApiException"
            and hasattr(exception, "status")
            and hasattr(exception, "http_resp")
        ):
            try:
                code = int(exception.status)
                # Validate it's a reasonable HTTP status code
                if _MIN_HTTP_STATUS_CODE <= code <= _MAX_HTTP_STATUS_CODE:
                    status_code = code
            except (ValueError, TypeError):
                # Invalid status value, fall back to default 500
                pass

        return cls(
            message=str(exception),
            status_code=status_code,
            uri=uri,
            tool_name=tool_name,
        )

    def _format_message(self) -> str:
        """Format error message to match original format exactly."""
        if self.tool_name and self.uri:
            return f"failed executing {self.tool_name} with URI: {self.uri},raised the following error: {self.message}"
        elif self.tool_name:
            return f"failed executing {self.tool_name}, raised the following error: {self.message}"
        elif self.uri:
            return f"with URI: {self.uri}, raised the following error: {self.message}"
        else:
            return self.message

    def __str__(self) -> str:
        return self._format_message()

    def __repr__(self) -> str:
        # Return the same format as __str__ for LangChain ToolNode
        # compatibility. LangChain uses repr(exception) when formatting
        # tool error messages
        return self._format_message()
