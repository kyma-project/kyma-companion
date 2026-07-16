"""Simple ReAct agent for Kyma — no supervisor, no subgraphs, no graph state.

Uses ``langchain.agents.create_agent`` which compiles a minimal two-node
(model → tools) loop.  The k8s_client is bound at construction so tools
do not need LangGraph's ``InjectedState`` machinery.

Usage::

    agent = KymaReActAgent(models=models, k8s_client=k8s_client)
    result = await agent.ainvoke("Why is my Kyma Function not starting?")
"""

from typing import Any, cast

from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from agents.common.data import Message
from agents.common.utils import get_relevant_context_from_k8s_cluster
from agents.k8s.tools.logs import POD_LOGS_TAIL_LINES_LIMIT
from agents.kyma.prompts import KYMA_AGENT_INSTRUCTIONS, KYMA_AGENT_PROMPT
from agents.kyma.tools.query import DEPRECATED_API_VERSIONS
from agents.kyma.tools.search import SearchKymaDocTool
from services.k8s import IK8sClient
from utils.models.factory import IModel
from utils.settings import MAIN_MODEL_NAME

SYSTEM_PROMPT = f"{KYMA_AGENT_PROMPT}\n\n{KYMA_AGENT_INSTRUCTIONS}"


class UINavigationContext(BaseModel):
    """Busola UI navigation context — the resource the user is currently viewing."""

    resource_kind: str
    resource_name: str = ""
    resource_api_version: str = ""
    namespace: str = ""

    def as_context_message(self) -> str:
        """Return a human-readable context string to prepend to the user query."""
        parts = []
        if self.resource_kind:
            parts.append(f"Resource kind: {self.resource_kind}")
        if self.resource_name:
            parts.append(f"Resource name: {self.resource_name}")
        if self.resource_api_version:
            parts.append(f"API version: {self.resource_api_version}")
        if self.namespace:
            parts.append(f"Namespace: {self.namespace}")
        if not parts:
            return ""
        return (
            "[Busola UI navigation context — the user is currently viewing this resource in the Kyma dashboard. "
            "Their question may or may not be about this resource.]\n" + "\n".join(parts)
        )


def _make_bound_tools(k8s_client: IK8sClient) -> list[BaseTool]:
    """Return tool instances with k8s_client pre-bound (avoids InjectedState outside LangGraph)."""

    class K8sQueryArgs(BaseModel):
        """Arguments for kyma_query_tool."""

        uri: str = Field(
            description="Kubernetes API URI path. Must follow the format of Kubernetes API paths. "
            "Examples for Kyma resources: '/apis/serverless.kyma-project.io/v1alpha2/namespaces/default/functions'. "
            "Examples for K8s resources: 1. '/api/v1/namespaces/default/pods', "
            "2. '/apis/apps/v1/namespaces/default/deployments'."
        )

    class ResourceVersionArgs(BaseModel):
        """Arguments for fetch_kyma_resource_version."""

        resource_kind: str = Field(
            description="Kind of Kyma resource to get the API version for (e.g., 'Function', 'APIRule'). "
            "Must be a valid Kyma resource kind available in the cluster."
        )

    class K8sOverviewArgs(BaseModel):
        """Arguments for k8s_overview_tool."""

        namespace: str = Field(
            description="Namespace to get an overview of. Use empty string '' for cluster-wide overview."
        )
        resource_kind: str = Field(
            description="Kind of resource to overview. Use 'cluster' for a full cluster overview, "
            "'namespace' for a namespace overview, or a specific resource kind like 'Pod', 'Deployment'."
        )

    class FetchPodLogsArgs(BaseModel):
        """Arguments for fetch_pod_logs_tool."""

        name: str = Field(description="Name of the pod.")
        namespace: str = Field(description="Namespace of the pod.")
        container_name: str = Field(description="Name of the container whose logs to fetch.")

    @tool(args_schema=K8sQueryArgs)
    async def kyma_query_tool(uri: str) -> dict | list[dict] | str:
        """Query any Kubernetes or Kyma resource using the provided URI.
        The URI must follow the Kubernetes API path format.
        Use this for both Kyma resources (Function, APIRule, etc.) and standard K8s resources
        (Pod, Deployment, Service, etc.).
        The returned data is sanitized to remove sensitive information (e.g. Secret data fields).
        If you get a 404, use fetch_kyma_resource_version to look up the correct API version and retry."""
        try:
            return await k8s_client.execute_get_api_request(uri)
        except Exception as e:
            return (
                f"Tool error ({e}). "
                "The API version or URI may be wrong — use fetch_kyma_resource_version "
                "to look up the correct API version for the resource kind and retry."
            )

    @tool(args_schema=ResourceVersionArgs)
    def fetch_kyma_resource_version(resource_kind: str) -> str:
        """Fetch the API version for a given Kyma resource kind.
        Example resource kinds: Function, APIRule, TracePipeline, etc.
        Use this when the resource version is not known, needs to be verified,
        or kyma_query_tool returns 404 not found."""
        try:
            version = k8s_client.get_resource_version(resource_kind)
            if version in DEPRECATED_API_VERSIONS:
                _, warning = DEPRECATED_API_VERSIONS[version]
                return f"{version}\nWARNING: {warning}"
            return version
        except Exception as e:
            return f"Tool error: could not fetch resource version for {resource_kind!r}: {e}"

    @tool(args_schema=K8sOverviewArgs)
    async def k8s_overview_tool(namespace: str, resource_kind: str) -> str:
        """Fetch a high-level overview of a Kubernetes cluster or namespace.
        Use namespace='' and resource_kind='cluster' for a full cluster overview.
        Use a specific namespace and resource_kind='namespace' for a namespace overview.
        Use a specific resource_kind (e.g. 'Pod', 'Deployment') to scope the overview."""
        try:
            message = Message(
                resource_kind=resource_kind,
                namespace=namespace,
                query="",
                resource_api_version="",
                resource_name="",
            )
            return await get_relevant_context_from_k8s_cluster(message, k8s_client)
        except Exception as e:
            return f"Tool error fetching K8s overview for namespace={namespace!r}, resource_kind={resource_kind!r}: {e}"

    @tool(args_schema=FetchPodLogsArgs)
    async def fetch_pod_logs_tool(name: str, namespace: str, container_name: str) -> str:
        """Fetch logs from a Kubernetes pod container.
        Returns current and previous logs, plus diagnostic context if logs are unavailable.
        Use this to investigate pod crashes, errors, or unexpected behaviour."""
        try:
            result = await k8s_client.fetch_pod_logs(name, namespace, container_name, POD_LOGS_TAIL_LINES_LIMIT)
            dumped = result.model_dump(mode="json", by_alias=True)
            return str(dumped)
        except Exception as e:
            return (
                f"Tool error fetching logs for pod={name!r}, namespace={namespace!r}, container={container_name!r}: {e}"
            )

    return [fetch_kyma_resource_version, kyma_query_tool, k8s_overview_tool, fetch_pod_logs_tool]


class KymaReActAgent:
    """ReAct agent using the same tools and prompts as KymaAgent.

    Unlike the graph-based KymaAgent this class:
    - Requires no LangGraph state, supervisor, or subgraph wiring
    - Accepts a query string and returns a string answer directly
    - Supports optional multi-turn chat_history
    """

    def __init__(
        self,
        models: dict[str, IModel | Embeddings],
        k8s_client: IK8sClient,
        search_tool: SearchKymaDocTool | None = None,
    ) -> None:
        """Initialize the agent with the given models, k8s_client, and search_tool."""
        resolved_search_tool = search_tool if search_tool is not None else SearchKymaDocTool(models)
        tools: list[BaseTool] = [*_make_bound_tools(k8s_client), resolved_search_tool]

        llm: BaseChatModel = cast(IModel, models[MAIN_MODEL_NAME]).llm
        self._graph = create_agent(
            model=llm,
            tools=tools,
            system_prompt=SystemMessage(content=SYSTEM_PROMPT),
        )

    async def ainvoke(
        self,
        query: str,
        chat_history: list[BaseMessage] | None = None,
        ui_context: UINavigationContext | None = None,
        callbacks: list[BaseCallbackHandler] | None = None,
    ) -> str:
        """Run the ReAct loop and return the final answer as a string."""
        human_content = query
        if ui_context is not None:
            human_content = f"{ui_context.as_context_message()}\n\n{query}"
        messages = [*(chat_history or []), HumanMessage(content=human_content)]
        payload: Any = {"messages": messages}
        run_config = RunnableConfig(callbacks=callbacks) if callbacks else None
        result = await self._graph.ainvoke(payload, config=run_config)
        messages_out = result.get("messages", [])
        if not messages_out:
            raise ValueError("KymaReActAgent: graph returned no messages")
        last = messages_out[-1]
        return str(last.content)
