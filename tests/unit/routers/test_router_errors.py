"""
Tests for K8s API error handling in router endpoints.

These tests verify that the router correctly extracts status codes from
K8sClientError and converts them to HTTPException with the same status code.
"""

from http import HTTPStatus
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from routers.common import K8sQueryRequest
from routers.k8s_tools_api import query_k8s_resource
from services.k8s import K8sClientError


class TestK8sAPIErrorHandling:
    """Test K8s API error handling in route handlers.

    These tests verify that the router correctly handles K8sClientError
    exceptions from tools and converts them to HTTPException with the
    correct status codes.
    """

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status_code,error_message,expected_status,test_description",
        [
            (401, "Unauthorized", HTTPStatus.UNAUTHORIZED, "authentication error"),
            (403, "Forbidden", HTTPStatus.FORBIDDEN, "authorization error"),
            (404, "Not Found", HTTPStatus.NOT_FOUND, "resource not found"),
            (
                503,
                "Service Unavailable",
                HTTPStatus.SERVICE_UNAVAILABLE,
                "service unavailable",
            ),
            (
                500,
                "Internal error",
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "internal server error",
            ),
        ],
    )
    async def test_router_handles_k8s_client_error_status_codes(
        self, status_code, error_message, expected_status, test_description
    ):
        """Test that router correctly extracts status_code from K8sClientError."""
        request = K8sQueryRequest(uri="/api/v1/namespaces/default/pods")

        # Mock k8s_query_tool to raise K8sClientError with specific status_code
        with patch("routers.k8s_tools_api.k8s_query_tool") as mock_tool:
            mock_tool.ainvoke = AsyncMock(
                side_effect=K8sClientError(
                    message=error_message,
                    status_code=status_code,
                    uri=request.uri,
                    tool_name="k8s_query_tool",
                )
            )

            with pytest.raises(HTTPException) as exc_info:
                await query_k8s_resource(request, None)  # k8s_client not used

            assert (
                exc_info.value.status_code == expected_status
            ), f"Failed: {test_description} - expected {expected_status}, got {exc_info.value.status_code}"
            assert "error" in exc_info.value.detail.lower()
