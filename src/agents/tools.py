"""Tool registry with decorator-based registration.

Adding a new tool requires only:
1. Define an async handler function
2. Decorate it with @tool_registry.tool(name, description, parameters)

The schema, dispatch, and handler are all in one place.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from http import HTTPStatus
from typing import Any

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from agents.common.data import Message
from agents.common.utils import get_relevant_context_from_k8s_cluster
from rag.system import Query
from services.k8s import IK8sClient
from utils.exceptions import K8sClientError, NoLogsAvailableError
from utils.logging import get_logger

logger = get_logger(__name__)

POD_LOGS_TAIL_LINES_LIMIT: int = 10

# HTTP status codes worth retrying (transient failures)
_RETRYABLE_STATUS_CODES = frozenset({
    HTTPStatus.TOO_MANY_REQUESTS,  # 429
    HTTPStatus.INTERNAL_SERVER_ERROR,  # 500
    HTTPStatus.BAD_GATEWAY,  # 502
    HTTPStatus.SERVICE_UNAVAILABLE,  # 503
    HTTPStatus.GATEWAY_TIMEOUT,  # 504
})


def _is_retryable(exc: BaseException) -> bool:
    """Return True if the exception is a transient K8s error worth retrying."""
    if isinstance(exc, K8sClientError):
        return exc.status_code in _RETRYABLE_STATUS_CODES
    return isinstance(exc, (TimeoutError, OSError, ConnectionError))


_k8s_retry = retry(
    retry=retry_if_exception(_is_retryable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)


# --- Tool definition dataclass ---


@dataclass
class ToolDef:
    """A registered tool with its schema and handler."""

    name: str
    description: str
    parameters: dict[str, Any]
    required: list[str]
    handler: Callable[..., Coroutine]
    enabled: Callable[["ToolRegistry"], bool] = field(default=lambda _: True)

    def schema(self) -> dict:
        """Return the OpenAI function-calling schema for this tool."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required,
                },
            },
        }


# --- Tool Registry ---


class ToolRegistry:
    """Registry of all available tools with decorator-based registration.

    Usage:
        registry = ToolRegistry()

        @registry.tool(
            name="my_tool",
            description="Does something useful",
            parameters={"arg1": {"type": "string", "description": "..."}},
            required=["arg1"],
        )
        async def my_tool(args, k8s_client, registry):
            return await k8s_client.do_something(args["arg1"])
    """

    def __init__(self, rag_system: Any | None = None):
        self._rag_system = rag_system
        self._tools: dict[str, ToolDef] = {}
        self._register_builtin_tools()

    def tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        required: list[str] | None = None,
        enabled: Callable[["ToolRegistry"], bool] | None = None,
        with_retry: bool = False,
    ) -> Callable:
        """Decorator to register a tool.

        Args:
            name: Tool name (used by the LLM to call it).
            description: What the tool does (sent to the LLM).
            parameters: OpenAI-style parameter definitions.
            required: List of required parameter names.
            enabled: Optional callable that receives the registry and returns bool.
                     If False, the tool is excluded from schemas and dispatch.
            with_retry: If True, wrap the handler with K8s retry logic.
        """

        def decorator(fn: Callable) -> Callable:
            handler = _k8s_retry(fn) if with_retry else fn
            tool_def = ToolDef(
                name=name,
                description=description,
                parameters=parameters,
                required=required or [],
                handler=handler,
                enabled=enabled or (lambda _: True),
            )
            self._tools[name] = tool_def
            return fn

        return decorator

    def get_tool_schemas(self) -> list[dict]:
        """Return schemas for all enabled tools."""
        return [
            td.schema()
            for td in self._tools.values()
            if td.enabled(self)
        ]

    async def execute_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        k8s_client: IK8sClient,
    ) -> str:
        """Execute a tool by name."""
        try:
            if name not in self._tools:
                raise ValueError(f"Unknown tool: {name}")
            result = await self._tools[name].handler(arguments, k8s_client, self)
            if isinstance(result, (dict, list)):
                return json.dumps(result, default=str)
            return str(result)
        except (K8sClientError, NoLogsAvailableError) as e:
            return json.dumps({"error": str(e)}, default=str)
        except Exception as e:
            logger.exception(f"Tool '{name}' execution failed")
            return json.dumps({"error": f"Tool execution failed: {e}"}, default=str)

    def _register_builtin_tools(self) -> None:
        """Register all built-in tools."""

        @self.tool(
            name="k8s_query_tool",
            description=(
                "Query the state of objects in Kubernetes using the provided URI. "
                "The URI must follow the format of Kubernetes API. "
                "The returned data is sanitized to remove any sensitive information. "
                "For example, it will always remove the `data` field of a `Secret` object."
            ),
            parameters={
                "uri": {
                    "type": "string",
                    "description": "Kubernetes API URI path, e.g. /api/v1/namespaces/default/pods",
                },
            },
            required=["uri"],
            with_retry=True,
        )
        async def k8s_query_tool(args: dict, k8s_client: IK8sClient, registry: ToolRegistry) -> dict | list[dict]:
            uri = args["uri"]
            try:
                return await k8s_client.execute_get_api_request(uri)
            except K8sClientError as e:
                if not e.tool_name:
                    e.tool_name = "k8s_query_tool"
                raise
            except Exception as e:
                raise K8sClientError.from_exception(exception=e, tool_name="k8s_query_tool", uri=uri) from e

        @self.tool(
            name="k8s_overview_query_tool",
            description=(
                "Fetch relevant context data from a Kubernetes cluster. "
                'To get an overview of cluster - use namespace="", resource_kind="cluster". '
                'To get an overview of namespace - provide namespace and resource_kind="namespace".'
            ),
            parameters={
                "namespace": {
                    "type": "string",
                    "description": "Kubernetes namespace (empty string for cluster-wide)",
                },
                "resource_kind": {
                    "type": "string",
                    "description": 'Resource kind: "cluster" or "namespace"',
                },
            },
            required=["namespace", "resource_kind"],
            with_retry=True,
        )
        async def k8s_overview_query_tool(args: dict, k8s_client: IK8sClient, registry: ToolRegistry) -> str:
            message = Message(
                resource_kind=args["resource_kind"],
                namespace=args["namespace"],
                query="",
                resource_api_version="",
                resource_name="",
            )
            return await get_relevant_context_from_k8s_cluster(message, k8s_client)

        @self.tool(
            name="kyma_query_tool",
            description=(
                "Query the state of Kyma resources in the cluster using the provided URI. "
                "The URI must follow the format of Kubernetes API. "
                "Use this to get information about Kyma-specific resources like Function, APIRule, etc. "
                "Example URIs: "
                "/apis/serverless.kyma-project.io/v1alpha2/namespaces/default/functions, "
                "/apis/gateway.kyma-project.io/v1beta1/namespaces/default/apirules"
            ),
            parameters={
                "uri": {
                    "type": "string",
                    "description": (
                        "Kubernetes API URI path for querying Kyma resources. "
                        "Must follow the format of Kubernetes API paths."
                    ),
                },
            },
            required=["uri"],
            with_retry=True,
        )
        async def kyma_query_tool(args: dict, k8s_client: IK8sClient, registry: ToolRegistry) -> dict | list[dict]:
            uri = args["uri"]
            try:
                return await k8s_client.execute_get_api_request(uri)
            except K8sClientError as e:
                if not e.tool_name:
                    e.tool_name = "kyma_query_tool"
                raise
            except Exception as e:
                raise K8sClientError.from_exception(exception=e, tool_name="kyma_query_tool", uri=uri) from e

        @self.tool(
            name="fetch_kyma_resource_version",
            description=(
                "Fetch the resource version for a given Kyma resource kind. "
                "Use this to get the API version when the resource version is not known or "
                "needs to be verified or kyma_query_tool returns 404 not found. "
                "Example resource kinds: Function, APIRule, TracePipeline, etc."
            ),
            parameters={
                "resource_kind": {
                    "type": "string",
                    "description": (
                        "Kind of Kyma resource (e.g., 'Function', 'APIRule', 'ServiceInstance'). "
                        "Must be a valid Kyma resource kind available in the cluster."
                    ),
                },
            },
            required=["resource_kind"],
            with_retry=True,
        )
        async def fetch_kyma_resource_version(args: dict, k8s_client: IK8sClient, registry: ToolRegistry) -> str:
            resource_kind = args["resource_kind"]
            try:
                return await k8s_client.get_resource_version(resource_kind)
            except Exception as e:
                raise K8sClientError.from_exception(
                    exception=e, tool_name="fetch_kyma_resource_version"
                ) from e

        @self.tool(
            name="fetch_pod_logs_tool",
            description=(
                "Fetch logs of Kubernetes Pod. Returns structured response with "
                "current and previous logs, plus diagnostic context if current logs are unavailable."
            ),
            parameters={
                "name": {"type": "string", "description": "Pod name"},
                "namespace": {"type": "string", "description": "Pod namespace"},
                "container_name": {"type": "string", "description": "Container name within the pod"},
            },
            required=["name", "namespace", "container_name"],
        )
        async def fetch_pod_logs_tool(args: dict, k8s_client: IK8sClient, registry: ToolRegistry) -> dict:
            try:
                result = await k8s_client.fetch_pod_logs(
                    args["name"],
                    args["namespace"],
                    args["container_name"],
                    POD_LOGS_TAIL_LINES_LIMIT,
                )
                return result.model_dump(mode="json", by_alias=True)
            except NoLogsAvailableError:
                raise
            except Exception as e:
                raise K8sClientError.from_exception(exception=e, tool_name="fetch_pod_logs_tool") from e

        @self.tool(
            name="search_kyma_doc",
            description=(
                "Search through Kyma documentation for relevant information about "
                "Kyma concepts, features, components, resources, or troubleshooting. "
                "A query is required to search the documentation."
            ),
            parameters={
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant Kyma documentation",
                },
            },
            required=["query"],
            enabled=lambda reg: reg._rag_system is not None,
        )
        async def search_kyma_doc(args: dict, k8s_client: IK8sClient, registry: ToolRegistry) -> str:
            if registry._rag_system is None:
                return "Kyma documentation search is not available."

            query = Query(text=args["query"])
            relevant_docs = await registry._rag_system.aretrieve(query, top_k=5)
            contents = [doc.page_content for doc in relevant_docs if doc.page_content.strip()]
            if not contents:
                return "No relevant documentation found."
            return "\n\n -- next document -- \n\n".join(contents)
