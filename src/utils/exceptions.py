from http import HTTPStatus


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
        extracting status code if available.
        """
        # Extract status code if available (e.g., from ApiException)
        # ApiException.status can be either an int or a string
        status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR
        if hasattr(exception, "status"):
            status = exception.status
            if isinstance(status, int) or (
                isinstance(status, str) and status.isdigit()
            ):
                status_code = int(status)

        return cls(
            message=str(exception),
            status_code=status_code,
            uri=uri,
            tool_name=tool_name,
        )

    def _format_message(self) -> str:
        """Format error message to match original format exactly."""
        if self.tool_name and self.uri:
            return (
                f"failed executing {self.tool_name} with URI: {self.uri},"
                f"raised the following error: {self.message}"
            )
        elif self.tool_name:
            return (
                f"failed executing {self.tool_name}, "
                f"raised the following error: {self.message}"
            )
        elif self.uri:
            return (
                f"with URI: {self.uri}, " f"raised the following error: {self.message}"
            )
        else:
            return self.message

    def __str__(self) -> str:
        return self._format_message()

    def __repr__(self) -> str:
        # Return the same format as __str__ for LangChain ToolNode
        # compatibility. LangChain uses repr(exception) when formatting
        # tool error messages
        return self._format_message()
