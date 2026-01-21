"""
Tests for K8s API error handling in router endpoints.

These tests verify that Kubernetes API errors are properly caught and mapped
to correct HTTP status codes across all K8s tool endpoints.
"""

from http import HTTPStatus
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from routers.common import K8sOverviewRequest, K8sQueryRequest, PodLogsRequest
from routers.k8s_tools_api import get_k8s_overview, get_pod_logs, query_k8s_resource
from services.k8s import IK8sClient
from utils.exceptions import K8sClientError


class TestK8sAPIErrorHandling:
    """Test K8s API error handling in route handlers.

    Tests cover all three K8s tool endpoints:
    - query_k8s_resource (/query)
    - get_pod_logs (/pods/logs)
    - get_k8s_overview (/overview)

    Error scenarios tested:
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

    @pytest.fixture
    def endpoint_configs(self):
        """Configure all three endpoints with their tools and request objects."""
        return [
            {
                "name": "query",
                "tool_path": "routers.k8s_tools_api.k8s_query_tool",
                "tool_name": "k8s_query_tool",
                "handler": query_k8s_resource,
                "request": K8sQueryRequest(uri="/api/v1/namespaces/default/pods"),
                "tool_input": lambda req, client: {
                    "uri": req.uri,
                    "k8s_client": client,
                },
            },
            {
                "name": "logs",
                "tool_path": "routers.k8s_tools_api.fetch_pod_logs_tool",
                "tool_name": "fetch_pod_logs_tool",
                "handler": get_pod_logs,
                "request": PodLogsRequest(
                    name="test-pod",
                    namespace="default",
                    container_name="app",
                    is_terminated=False,
                ),
                "tool_input": lambda req, client: {
                    "name": req.name,
                    "namespace": req.namespace,
                    "container_name": req.container_name,
                    "is_terminated": req.is_terminated,
                    "k8s_client": client,
                },
            },
            {
                "name": "overview",
                "tool_path": "routers.k8s_tools_api.k8s_overview_query_tool",
                "tool_name": "k8s_overview_query_tool",
                "handler": get_k8s_overview,
                "request": K8sOverviewRequest(namespace="default", resource_kind="cluster"),
                "tool_input": lambda req, client: {
                    "namespace": req.namespace,
                    "resource_kind": req.resource_kind,
                    "k8s_client": client,
                },
            },
        ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "status_code,reason,expected_status,test_description",
        [
            (400, "Bad Request", HTTPStatus.BAD_REQUEST, "invalid request format"),
            (401, "Unauthorized", HTTPStatus.UNAUTHORIZED, "invalid credentials"),
            (403, "Forbidden", HTTPStatus.FORBIDDEN, "insufficient permissions"),
            (404, "Not Found", HTTPStatus.NOT_FOUND, "resource not found"),
            (409, "Conflict", HTTPStatus.CONFLICT, "resource already exists"),
            (
                422,
                "Unprocessable Entity",
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "validation failed",
            ),
            (
                429,
                "Too Many Requests",
                HTTPStatus.TOO_MANY_REQUESTS,
                "rate limit exceeded",
            ),
            (
                500,
                "Internal Server Error",
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "server error",
            ),
            (
                503,
                "Service Unavailable",
                HTTPStatus.SERVICE_UNAVAILABLE,
                "cluster unavailable",
            ),
        ],
    )
    async def test_api_exception_status_codes(
        self,
        mock_k8s_client,
        endpoint_configs,
        status_code,
        reason,
        expected_status,
        test_description,
    ):
        """Test that K8s API errors return correct HTTP status codes across all endpoints."""
        for config in endpoint_configs:
            with patch(config["tool_path"]) as mock_tool:
                mock_tool.ainvoke = AsyncMock(
                    side_effect=K8sClientError(
                        message=f"Kubernetes API error: {reason}",
                        status_code=status_code,
                        uri="/test",
                        tool_name=config["tool_name"],
                    )
                )

                with pytest.raises(HTTPException) as exc_info:
                    await config["handler"](config["request"], mock_k8s_client)

                assert exc_info.value.status_code == expected_status, (
                    f"Failed test case for {config['name']} endpoint: {test_description}"
                )
                assert "Kubernetes" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_non_k8s_exception_returns_500(self, mock_k8s_client, endpoint_configs):
        """Test that non-K8s exceptions return HTTP 500 across all endpoints.

        Non-K8sClientError errors (unexpected exceptions) should
        return 500 since they don't have HTTP status codes.
        """
        for config in endpoint_configs:
            with patch(config["tool_path"]) as mock_tool:
                mock_tool.ainvoke = AsyncMock(side_effect=Exception("Connection timeout"))

                with pytest.raises(HTTPException) as exc_info:
                    await config["handler"](config["request"], mock_k8s_client)

                assert exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR, (
                    f"Failed test case for {config['name']} endpoint"
                )
