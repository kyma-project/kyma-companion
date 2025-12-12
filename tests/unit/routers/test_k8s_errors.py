"""
Tests for K8s API error handling in router endpoints.

These tests verify that Kubernetes API errors are properly caught and mapped
to correct HTTP status codes after the lazy initialization.
"""

from http import HTTPStatus
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from kubernetes.client.exceptions import ApiException

from routers.common import K8sQueryRequest
from routers.k8s_tools_api import query_k8s_resource
from services.k8s import IK8sClient


class TestK8sAPIErrorHandling:
    """Test K8s API error handling in route handlers.

    Tests cover:
    - Authentication errors (401)
    - Authorization errors (403)
    - Resource not found (404)
    - Service unavailable (503)
    - Non-K8s exceptions (500)
    """

    @pytest.fixture
    def mock_k8s_client(self):
        """Create a mock K8s client."""
        return Mock(spec=IK8sClient)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status_code,reason,expected_status,test_description",
        [
            (401, "Unauthorized", HTTPStatus.UNAUTHORIZED, "invalid credentials"),
            (403, "Forbidden", HTTPStatus.FORBIDDEN, "insufficient permissions"),
            (404, "Not Found", HTTPStatus.NOT_FOUND, "resource not found"),
            (
                503,
                "Service Unavailable",
                HTTPStatus.SERVICE_UNAVAILABLE,
                "cluster unavailable",
            ),
        ],
    )
    async def test_api_exception_status_codes(
        self, mock_k8s_client, status_code, reason, expected_status, test_description
    ):
        """Test that K8s API errors return correct HTTP status codes."""
        request = K8sQueryRequest(uri="/api/v1/namespaces/default/pods")

        mock_k8s_client.execute_get_api_request = AsyncMock(
            side_effect=ApiException(status=status_code, reason=reason)
        )

        with pytest.raises(HTTPException) as exc_info:
            await query_k8s_resource(request, mock_k8s_client)

        assert (
            exc_info.value.status_code == expected_status
        ), f"Failed test case: {test_description}"
        assert "Kubernetes API error" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_non_k8s_exception_returns_500(self, mock_k8s_client):
        """Test that non-K8s exceptions return HTTP 500.

        Non-ApiException errors (network timeout, internal errors) should
        return 500 since they don't have HTTP status codes.
        """
        request = K8sQueryRequest(uri="/api/v1/namespaces/default/pods")

        # Mock a non-ApiException error (e.g., network timeout)
        mock_k8s_client.execute_get_api_request = AsyncMock(
            side_effect=Exception("Connection timeout")
        )

        with pytest.raises(HTTPException) as exc_info:
            await query_k8s_resource(request, mock_k8s_client)

        assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
