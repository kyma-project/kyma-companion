"""
Tests for Kyma API error handling in router endpoints.

These tests verify that Kubernetes API errors are properly caught and mapped
to correct HTTP status codes across Kyma tool endpoints that use K8sClientError.
"""

from http import HTTPStatus
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from routers.common import KymaQueryRequest, KymaResourceVersionRequest
from routers.kyma_tools_api import get_resource_version, query_kyma_resource
from services.k8s import IK8sClient
from utils.exceptions import K8sClientError


class TestKymaAPIErrorHandling:
    """Test Kyma API error handling in route handlers."""

    @pytest.fixture
    def mock_k8s_client(self):
        """Create a mock K8s client."""
        return Mock(spec=IK8sClient)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status_code,reason,expected_status,test_description",
        [
            (400, "Bad Request", HTTPStatus.BAD_REQUEST, "invalid request format"),
            (401, "Unauthorized", HTTPStatus.UNAUTHORIZED, "invalid credentials"),
            (403, "Forbidden", HTTPStatus.FORBIDDEN, "insufficient permissions"),
            (404, "Not Found", HTTPStatus.NOT_FOUND, "resource not found"),
            (409, "Conflict", HTTPStatus.CONFLICT, "resource already exists"),
            (422, "Unprocessable Entity", HTTPStatus.UNPROCESSABLE_ENTITY, "validation failed"),
            (429, "Too Many Requests", HTTPStatus.TOO_MANY_REQUESTS, "rate limit exceeded"),
            (500, "Internal Server Error", HTTPStatus.INTERNAL_SERVER_ERROR, "server error"),
            (503, "Service Unavailable", HTTPStatus.SERVICE_UNAVAILABLE, "cluster unavailable"),
        ],
    )
    async def test_query_endpoint_k8s_error_status_codes(
        self,
        mock_k8s_client,
        status_code,
        reason,
        expected_status,
        test_description,
    ):
        """Test that K8s API errors return correct HTTP status codes for query endpoint."""
        request = KymaQueryRequest(
            uri="/apis/serverless.kyma-project.io/v1alpha2/namespaces/default/functions"
        )
        error = K8sClientError(
            message=f"Kubernetes API error: {reason}",
            status_code=status_code,
            uri="/test",
            tool_name="kyma_query_tool",
        )
        mock_k8s_client.execute_get_api_request = AsyncMock(side_effect=error)

        with pytest.raises(HTTPException) as exc_info:
            await query_kyma_resource(request, mock_k8s_client)

        assert exc_info.value.status_code == expected_status, (
            f"Failed for query endpoint: {test_description}"
        )
        assert exc_info.value.detail is not None

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
    async def test_resource_version_endpoint_k8s_error_status_codes(
        self,
        mock_k8s_client,
        status_code,
        reason,
        expected_status,
        test_description,
    ):
        """Test that K8s API errors return correct HTTP status codes for resource-version endpoint."""
        request = KymaResourceVersionRequest(resource_kind="Function")
        error = K8sClientError(
            message=f"Kubernetes API error: {reason}",
            status_code=status_code,
            tool_name="fetch_kyma_resource_version",
        )
        mock_k8s_client.get_resource_version = AsyncMock(side_effect=error)

        with pytest.raises(HTTPException) as exc_info:
            await get_resource_version(request, mock_k8s_client)

        assert exc_info.value.status_code == expected_status, (
            f"Failed for resource-version endpoint: {test_description}"
        )

    @pytest.mark.asyncio
    async def test_query_non_k8s_exception_returns_500(self, mock_k8s_client):
        """Test that non-K8s exceptions return HTTP 500 for query endpoint."""
        request = KymaQueryRequest(
            uri="/apis/serverless.kyma-project.io/v1alpha2/namespaces/default/functions"
        )
        mock_k8s_client.execute_get_api_request = AsyncMock(side_effect=Exception("Connection timeout"))

        with pytest.raises(HTTPException) as exc_info:
            await query_kyma_resource(request, mock_k8s_client)

        assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_resource_version_non_k8s_exception_returns_500(self, mock_k8s_client):
        """Test that non-K8s exceptions return HTTP 500 for resource-version endpoint."""
        request = KymaResourceVersionRequest(resource_kind="Function")
        mock_k8s_client.get_resource_version = AsyncMock(side_effect=Exception("Connection timeout"))

        with pytest.raises(HTTPException) as exc_info:
            await get_resource_version(request, mock_k8s_client)

        assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
