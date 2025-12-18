"""
Tests for Kyma API error handling in router endpoints.

These tests verify that Kubernetes API errors are properly caught and mapped
to correct HTTP status codes across Kyma tool endpoints that use K8sClientError.
"""

from http import HTTPStatus
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

from routers.common import KymaQueryRequest, KymaResourceVersionRequest
from routers.kyma_tools_api import get_resource_version, query_kyma_resource
from services.k8s import IK8sClient
from utils.exceptions import K8sClientError


class TestKymaAPIErrorHandling:
    """Test Kyma API error handling in route handlers.

    Tests cover Kyma tool endpoints that interact with Kubernetes API:
    - query_kyma_resource (/query)
    - get_resource_version (/resource-version)

    Note: /search endpoint is not tested here as it doesn't use K8sClientError.

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
        """Configure both Kyma endpoints with their tools and request objects."""
        return [
            {
                "name": "query",
                "tool_path": "routers.kyma_tools_api.kyma_query_tool",
                "tool_name": "kyma_query_tool",
                "handler": query_kyma_resource,
                "request": KymaQueryRequest(
                    uri="/apis/serverless.kyma-project.io/v1alpha2/namespaces/default/functions"
                ),
                "is_async": True,
            },
            {
                "name": "resource-version",
                "tool_path": "routers.kyma_tools_api.fetch_kyma_resource_version",
                "tool_name": "fetch_kyma_resource_version",
                "handler": get_resource_version,
                "request": KymaResourceVersionRequest(resource_kind="Function"),
                "is_async": False,
            },
        ]

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
        self,
        mock_k8s_client,
        endpoint_configs,
        status_code,
        reason,
        expected_status,
        test_description,
    ):
        """Test that K8s API errors return correct HTTP status codes across Kyma endpoints."""
        for config in endpoint_configs:
            with patch(config["tool_path"]) as mock_tool:
                error = K8sClientError(
                    message=f"Kubernetes API error: {reason}",
                    status_code=status_code,
                    uri="/test",
                    tool_name=config["tool_name"],
                )

                if config["is_async"]:
                    mock_tool.ainvoke = AsyncMock(side_effect=error)
                else:
                    mock_tool.invoke = Mock(side_effect=error)

                with pytest.raises(HTTPException) as exc_info:
                    await config["handler"](config["request"], mock_k8s_client)

                assert (
                    exc_info.value.status_code == expected_status
                ), f"Failed test case for {config['name']} endpoint: {test_description}"
                # Note: Kyma endpoints have different detail formats
                # query endpoint uses dict, resource-version uses string
                assert exc_info.value.detail is not None

    @pytest.mark.asyncio
    async def test_non_k8s_exception_returns_500(
        self, mock_k8s_client, endpoint_configs
    ):
        """Test that non-K8s exceptions return HTTP 500 across Kyma endpoints.

        Non-K8sClientError errors (unexpected exceptions) should
        return 500 since they don't have HTTP status codes.
        """
        for config in endpoint_configs:
            with patch(config["tool_path"]) as mock_tool:
                error = Exception("Connection timeout")

                if config["is_async"]:
                    mock_tool.ainvoke = AsyncMock(side_effect=error)
                else:
                    mock_tool.invoke = Mock(side_effect=error)

                with pytest.raises(HTTPException) as exc_info:
                    await config["handler"](config["request"], mock_k8s_client)

                assert (
                    exc_info.value.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
                ), f"Failed test case for {config['name']} endpoint"
