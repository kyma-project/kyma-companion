"""Tests for ToolRegistry: schema generation, execution dispatch, and error handling."""

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from agents.tools import (
    POD_LOGS_TAIL_LINES_LIMIT,
    ToolRegistry,
)
from services.k8s_models import PodLogs, PodLogsResult
from utils.exceptions import K8sClientError, NoLogsAvailableError


@pytest.fixture
def mock_k8s_client():
    client = MagicMock()
    client.execute_get_api_request = AsyncMock(return_value={"items": []})
    client.get_resource_version = AsyncMock(return_value="v1")
    client.fetch_pod_logs = AsyncMock(
        return_value=PodLogsResult(
            logs=PodLogs(
                current_container="log line 1\nlog line 2",
                previously_terminated_container="Not available",
            ),
            status_code=200,
        )
    )
    client.list_not_running_pods = AsyncMock(return_value=[])
    client.list_nodes_metrics = AsyncMock(return_value=[])
    client.list_k8s_warning_events = AsyncMock(return_value=[])
    return client


@pytest.fixture
def registry():
    return ToolRegistry(rag_system=None)


@pytest.fixture
def registry_with_rag():
    mock_rag = Mock()
    return ToolRegistry(rag_system=mock_rag)


class TestToolRegistrySchemas:
    """Tests for get_tool_schemas method."""

    def test_schemas_without_rag(self, registry):
        """Without RAG system, search_kyma_doc is excluded."""
        schemas = registry.get_tool_schemas()
        names = [s["function"]["name"] for s in schemas]
        assert "k8s_query_tool" in names
        assert "k8s_overview_query_tool" in names
        assert "kyma_query_tool" in names
        assert "fetch_kyma_resource_version" in names
        assert "fetch_pod_logs_tool" in names
        assert "search_kyma_doc" not in names
        assert len(schemas) == 5

    def test_schemas_with_rag(self, registry_with_rag):
        """With RAG system, search_kyma_doc is included."""
        schemas = registry_with_rag.get_tool_schemas()
        names = [s["function"]["name"] for s in schemas]
        assert "search_kyma_doc" in names
        assert len(schemas) == 6

    @pytest.mark.parametrize("schema_index", range(6))
    def test_schema_structure(self, registry_with_rag, schema_index):
        """Each tool schema has the required OpenAI function-calling structure."""
        schemas = registry_with_rag.get_tool_schemas()
        schema = schemas[schema_index]
        assert schema["type"] == "function"
        func = schema["function"]
        assert "name" in func
        assert "description" in func
        assert "parameters" in func
        assert func["parameters"]["type"] == "object"
        assert "properties" in func["parameters"]
        assert "required" in func["parameters"]


class TestToolRegistryDispatch:
    """Tests for execute_tool dispatch to correct handlers."""

    @pytest.mark.asyncio
    async def test_dispatch_k8s_query(self, registry, mock_k8s_client):
        """k8s_query_tool dispatches to execute_get_api_request."""
        mock_k8s_client.execute_get_api_request = AsyncMock(return_value={"kind": "Pod"})
        result = await registry.execute_tool(
            "k8s_query_tool",
            {"uri": "/api/v1/namespaces/default/pods"},
            mock_k8s_client,
        )
        parsed = json.loads(result)
        assert parsed["kind"] == "Pod"
        mock_k8s_client.execute_get_api_request.assert_called_once_with("/api/v1/namespaces/default/pods")

    @pytest.mark.asyncio
    async def test_dispatch_kyma_query(self, registry, mock_k8s_client):
        """kyma_query_tool dispatches to execute_get_api_request."""
        mock_k8s_client.execute_get_api_request = AsyncMock(return_value={"kind": "Function"})
        result = await registry.execute_tool(
            "kyma_query_tool",
            {"uri": "/apis/serverless.kyma-project.io/v1alpha2/functions"},
            mock_k8s_client,
        )
        parsed = json.loads(result)
        assert parsed["kind"] == "Function"

    @pytest.mark.asyncio
    async def test_dispatch_fetch_resource_version(self, registry, mock_k8s_client):
        """fetch_kyma_resource_version dispatches to get_resource_version."""
        mock_k8s_client.get_resource_version = AsyncMock(return_value="serverless.kyma-project.io/v1alpha2")
        result = await registry.execute_tool(
            "fetch_kyma_resource_version",
            {"resource_kind": "Function"},
            mock_k8s_client,
        )
        assert "serverless.kyma-project.io/v1alpha2" in result

    @pytest.mark.asyncio
    async def test_dispatch_fetch_pod_logs(self, registry, mock_k8s_client):
        """fetch_pod_logs_tool dispatches to fetch_pod_logs."""
        result = await registry.execute_tool(
            "fetch_pod_logs_tool",
            {"name": "my-pod", "namespace": "default", "container_name": "app"},
            mock_k8s_client,
        )
        parsed = json.loads(result)
        assert "logs" in parsed
        mock_k8s_client.fetch_pod_logs.assert_called_once_with("my-pod", "default", "app", POD_LOGS_TAIL_LINES_LIMIT)

    @pytest.mark.asyncio
    async def test_dispatch_k8s_overview_query(self, registry, mock_k8s_client):
        """k8s_overview_query_tool dispatches correctly."""
        with patch(
            "agents.tools.get_relevant_context_from_k8s_cluster",
            new_callable=AsyncMock,
            return_value="overview data",
        ):
            result = await registry.execute_tool(
                "k8s_overview_query_tool",
                {"namespace": "default", "resource_kind": "namespace"},
                mock_k8s_client,
            )
            assert "overview data" in result


class TestToolRegistryErrorHandling:
    """Tests for error handling in execute_tool."""

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self, registry, mock_k8s_client):
        """Unknown tool name returns JSON error."""
        result = await registry.execute_tool("nonexistent_tool", {}, mock_k8s_client)
        parsed = json.loads(result)
        assert "error" in parsed
        assert "Unknown tool" in parsed["error"]

    @pytest.mark.asyncio
    async def test_k8s_client_error_returned_as_json(self, registry, mock_k8s_client):
        """K8sClientError is caught and returned as JSON."""
        mock_k8s_client.execute_get_api_request = AsyncMock(
            side_effect=K8sClientError(message="Not found", status_code=404, uri="/api/v1/pods")
        )
        result = await registry.execute_tool("k8s_query_tool", {"uri": "/api/v1/pods"}, mock_k8s_client)
        parsed = json.loads(result)
        assert "error" in parsed

    @pytest.mark.asyncio
    async def test_no_logs_error_returned_as_json(self, registry, mock_k8s_client):
        """NoLogsAvailableError is caught and returned as JSON."""
        mock_k8s_client.fetch_pod_logs = AsyncMock(
            side_effect=NoLogsAvailableError(
                message="No logs",
                pod="my-pod",
                namespace="default",
                container="app",
            )
        )
        result = await registry.execute_tool(
            "fetch_pod_logs_tool",
            {"name": "my-pod", "namespace": "default", "container_name": "app"},
            mock_k8s_client,
        )
        parsed = json.loads(result)
        assert "error" in parsed

    @pytest.mark.asyncio
    async def test_generic_exception_returned_as_json(self, registry, mock_k8s_client):
        """Generic exceptions are caught and returned as JSON error."""
        mock_k8s_client.execute_get_api_request = AsyncMock(side_effect=RuntimeError("unexpected"))
        result = await registry.execute_tool("k8s_query_tool", {"uri": "/api/v1/pods"}, mock_k8s_client)
        parsed = json.loads(result)
        assert "error" in parsed


class TestToolRegistrySearchKymaDoc:
    """Tests for search_kyma_doc tool."""

    @pytest.mark.asyncio
    async def test_search_without_rag_system(self, registry, mock_k8s_client):
        """Without RAG system, returns unavailable message."""
        result = await registry.execute_tool("search_kyma_doc", {"query": "what is function"}, mock_k8s_client)
        assert "not available" in result.lower()

    @pytest.mark.asyncio
    async def test_search_with_rag_system(self, mock_k8s_client):
        """With RAG system, returns document content."""
        mock_doc = Mock()
        mock_doc.page_content = "Kyma Functions are serverless functions."
        mock_rag = AsyncMock()
        mock_rag.aretrieve = AsyncMock(return_value=[mock_doc])

        registry = ToolRegistry(rag_system=mock_rag)
        with patch("rag.system.Query", autospec=True):
            result = await registry.execute_tool("search_kyma_doc", {"query": "what is function"}, mock_k8s_client)
        assert "serverless functions" in result

    @pytest.mark.asyncio
    async def test_search_with_no_results(self, mock_k8s_client):
        """When RAG returns empty results, returns no docs found message."""
        mock_rag = AsyncMock()
        mock_rag.aretrieve = AsyncMock(return_value=[])

        registry = ToolRegistry(rag_system=mock_rag)
        with patch("rag.system.Query", autospec=True):
            result = await registry.execute_tool("search_kyma_doc", {"query": "nonexistent topic"}, mock_k8s_client)
        assert "No relevant documentation found" in result
