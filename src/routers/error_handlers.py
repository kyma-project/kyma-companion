"""
Unified error handling for FastAPI routers.

This module provides decorators for consistent error handling across tool endpoints.
"""

from collections.abc import Callable
from functools import wraps
from http import HTTPStatus
from typing import Any, TypeVar

from fastapi import HTTPException

from utils.exceptions import K8sClientError
from utils.logging import get_logger

logger = get_logger(__name__)

# Type variable for generic function signature preservation
F = TypeVar("F", bound=Callable[..., Any])


def handle_tool_errors(operation_name: str) -> Callable[[F], F]:
    """
    Decorator that provides unified error handling for tool endpoints.

    Catches K8sClientError and generic exceptions, logs them appropriately,
    and converts them to FastAPI HTTPExceptions with structured error responses.

    Args:
        operation_name: Human-readable name of the operation for logging (e.g., "K8s query")

    Example:
        @router.post("/query")
        @handle_tool_errors("K8s query")
        async def query_k8s_resource(...):
            return await k8s_query_tool.ainvoke(...)

    Returns:
        Decorated function with automatic error handling
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except K8sClientError as e:
                logger.error(
                    f"{operation_name} failed: {e.status_code} - {e.message}",
                    extra={"uri": e.uri, "tool_name": e.tool_name},
                )
                raise HTTPException(
                    status_code=e.status_code,
                    detail=f"Kubernetes error: {e.message}",
                ) from e
            except Exception as e:
                logger.exception(f"{operation_name} unexpected error: {str(e)}")
                raise HTTPException(
                    status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                    detail=f"{operation_name} failed: {str(e)}",
                ) from e

        return wrapper  # type: ignore

    return decorator
