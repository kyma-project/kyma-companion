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
    async def test_invalid_credentials_returns_401(self, mock_k8s_client):
        """Test that invalid K8s credentials return HTTP 401."""
        request = K8sQueryRequest(uri="/api/v1/namespaces/default/pods")

        # Mock k8s_client.execute_get_api_request to raise ApiException
        mock_k8s_client.execute_get_api_request = AsyncMock(
            side_effect=ApiException(status=401, reason="Unauthorized")
        )

        with pytest.raises(HTTPException) as exc_info:
            await query_k8s_resource(request, mock_k8s_client)

        assert exc_info.value.status_code == HTTPStatus.UNAUTHORIZED
        assert "Kubernetes API error" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_insufficient_permissions_returns_403(self, mock_k8s_client):
        """Test that insufficient RBAC permissions return HTTP 403."""
        request = K8sQueryRequest(uri="/api/v1/namespaces/default/secrets")

        mock_k8s_client.execute_get_api_request = AsyncMock(
            side_effect=ApiException(status=403, reason="Forbidden")
        )

        with pytest.raises(HTTPException) as exc_info:
            await query_k8s_resource(request, mock_k8s_client)

        assert exc_info.value.status_code == HTTPStatus.FORBIDDEN
        assert "Kubernetes API error" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_resource_not_found_returns_404(self, mock_k8s_client):
        """Test that K8s resource not found returns HTTP 404."""
        request = K8sQueryRequest(uri="/api/v1/namespaces/nonexistent/pods")

        mock_k8s_client.execute_get_api_request = AsyncMock(
            side_effect=ApiException(status=404, reason="Not Found")
        )

        with pytest.raises(HTTPException) as exc_info:
            await query_k8s_resource(request, mock_k8s_client)

        assert exc_info.value.status_code == HTTPStatus.NOT_FOUND
        assert "Kubernetes API error" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_cluster_unavailable_returns_503(self, mock_k8s_client):
        """Test that cluster unavailable returns HTTP 503."""
        request = K8sQueryRequest(uri="/api/v1/namespaces/default/pods")

        mock_k8s_client.execute_get_api_request = AsyncMock(
            side_effect=ApiException(status=503, reason="Service Unavailable")
        )

        with pytest.raises(HTTPException) as exc_info:
            await query_k8s_resource(request, mock_k8s_client)

        assert exc_info.value.status_code == HTTPStatus.SERVICE_UNAVAILABLE
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
        assert "K8s query failed" in exc_info.value.detail
