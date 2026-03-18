"""
Tests for K8s API error handling in router endpoints.

These tests verify that Kubernetes API errors are properly caught and mapped
to correct HTTP status codes across all K8s tool endpoints.
"""

from http import HTTPStatus
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException, Response

from routers.common import K8sOverviewRequest, K8sQueryRequest, PodLogsRequest
from routers.k8s_tools_api import get_k8s_overview, get_pod_logs, query_k8s_resource
from services.k8s import IK8sClient
from utils.exceptions import K8sClientError


class TestK8sAPIErrorHandling:
    """Test K8s API error handling in route handlers."""

    @pytest.fixture
    def mock_k8s_client(self):
        return Mock(spec=IK8sClient)

    @pytest.fixture
    def mock_response(self):
        return Mock(spec=Response)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status_code,reason,expected_status,test_description",
        [
            (400, "Bad Request", HTTPStatus.BAD_REQUEST, "invalid request format"),
            (401, "Unauthorized", HTTPStatus.UNAUTHORIZED, "invalid credentials"),
            (403, "Forbidden", HTTPStatus.FORBIDDEN, "insufficient permissions"),
            (404, "Not Found", HTTPStatus.NOT_FOUND, "resource not found"),
            (500, "Internal Server Error", HTTPStatus.INTERNAL_SERVER_ERROR, "server error"),
            (503, "Service Unavailable", HTTPStatus.SERVICE_UNAVAILABLE, "cluster unavailable"),
        ],
    )
    async def test_query_endpoint_k8s_error(
        self, mock_k8s_client, status_code, reason, expected_status, test_description
    ):
        """Test query endpoint handles K8sClientError with correct status codes."""
        request = K8sQueryRequest(uri="/api/v1/namespaces/default/pods")
        mock_k8s_client.execute_get_api_request = AsyncMock(
            side_effect=K8sClientError(
                message=f"Kubernetes API error: {reason}",
                status_code=status_code,
                uri=request.uri,
            )
        )

        with pytest.raises(HTTPException) as exc_info:
            await query_k8s_resource(request, mock_k8s_client)

        assert exc_info.value.status_code == expected_status, f"Failed: {test_description}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status_code,reason,expected_status,test_description",
        [
            (401, "Unauthorized", HTTPStatus.UNAUTHORIZED, "invalid credentials"),
            (403, "Forbidden", HTTPStatus.FORBIDDEN, "insufficient permissions"),
            (404, "Not Found", HTTPStatus.NOT_FOUND, "resource not found"),
            (500, "Internal Server Error", HTTPStatus.INTERNAL_SERVER_ERROR, "server error"),
        ],
    )
    async def test_pod_logs_endpoint_k8s_error(
        self, mock_k8s_client, mock_response, status_code, reason, expected_status, test_description
    ):
        """Test pod logs endpoint handles K8sClientError with correct status codes."""
        request = PodLogsRequest(name="test-pod", namespace="default", container_name="app")
        mock_k8s_client.fetch_pod_logs = AsyncMock(
            side_effect=K8sClientError(
                message=f"Kubernetes API error: {reason}",
                status_code=status_code,
            )
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_pod_logs(request, mock_k8s_client, mock_response)

        assert exc_info.value.status_code == expected_status, f"Failed: {test_description}"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status_code,reason,expected_status,test_description",
        [
            (401, "Unauthorized", HTTPStatus.UNAUTHORIZED, "invalid credentials"),
            (403, "Forbidden", HTTPStatus.FORBIDDEN, "insufficient permissions"),
            (500, "Internal Server Error", HTTPStatus.INTERNAL_SERVER_ERROR, "server error"),
        ],
    )
    async def test_overview_endpoint_k8s_error(
        self, mock_k8s_client, status_code, reason, expected_status, test_description
    ):
        """Test overview endpoint handles K8sClientError with correct status codes."""
        request = K8sOverviewRequest(namespace="", resource_kind="cluster")
        mock_k8s_client.list_not_running_pods = AsyncMock(
            side_effect=K8sClientError(
                message=f"Kubernetes API error: {reason}",
                status_code=status_code,
            )
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_k8s_overview(request, mock_k8s_client)

        assert exc_info.value.status_code == expected_status, f"Failed: {test_description}"

    @pytest.mark.asyncio
    async def test_query_non_k8s_exception_returns_500(self, mock_k8s_client):
        """Test that unexpected exceptions return HTTP 500."""
        request = K8sQueryRequest(uri="/api/v1/namespaces/default/pods")
        mock_k8s_client.execute_get_api_request = AsyncMock(side_effect=Exception("Connection timeout"))

        with pytest.raises(HTTPException) as exc_info:
            await query_k8s_resource(request, mock_k8s_client)

        assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_pod_logs_non_k8s_exception_returns_500(self, mock_k8s_client, mock_response):
        """Test that unexpected exceptions return HTTP 500."""
        request = PodLogsRequest(name="test-pod", namespace="default", container_name="app")
        mock_k8s_client.fetch_pod_logs = AsyncMock(side_effect=Exception("Connection timeout"))

        with pytest.raises(HTTPException) as exc_info:
            await get_pod_logs(request, mock_k8s_client, mock_response)

        assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_overview_non_k8s_exception_returns_500(self, mock_k8s_client):
        """Test that unexpected exceptions return HTTP 500."""
        request = K8sOverviewRequest(namespace="default", resource_kind="cluster")
        mock_k8s_client.list_not_running_pods = AsyncMock(side_effect=Exception("Connection timeout"))

        with pytest.raises(HTTPException) as exc_info:
            await get_k8s_overview(request, mock_k8s_client)

        assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
