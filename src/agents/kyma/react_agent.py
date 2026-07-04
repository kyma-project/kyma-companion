"""Simple ReAct agent for Kyma — no supervisor, no subgraphs, no graph state.

Uses ``langchain.agents.create_agent`` which compiles a minimal two-node
(model → tools) loop.  The k8s_client is bound at construction so tools
do not need LangGraph's ``InjectedState`` machinery.

Usage::

    agent = KymaReActAgent(models=models, k8s_client=k8s_client)
    result = await agent.ainvoke("Why is my Kyma Function not starting?")
    print(result)
"""

from typing import Any

from langchain.agents import create_agent
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

from agents.kyma.prompts import KYMA_AGENT_INSTRUCTIONS, KYMA_AGENT_PROMPT
from agents.kyma.tools.query import DEPRECATED_API_VERSIONS
from agents.kyma.tools.search import SearchKymaDocTool
from services.k8s import IK8sClient
from utils.exceptions import K8sClientError
from utils.models.factory import IModel

SYSTEM_PROMPT = f"{KYMA_AGENT_PROMPT}\n\n{KYMA_AGENT_INSTRUCTIONS}"


def _make_bound_tools(k8s_client: IK8sClient) -> list[BaseTool]:
    """Return tool instances with k8s_client pre-bound (avoids InjectedState outside LangGraph)."""

    class KymaQueryArgs(BaseModel):
        """Arguments for kyma_query_tool."""

        uri: str = Field(
            description="Kubernetes API URI path for querying Kyma resources. "
            "Must follow the format of Kubernetes API paths like "
            "'/apis/serverless.kyma-project.io/v1alpha2/namespaces/default/functions'."
        )

    class KymaResourceVersionArgs(BaseModel):
        """Arguments for fetch_kyma_resource_version."""

        resource_kind: str = Field(
            description="Kind of Kyma resource to get the version for (e.g., 'Function', 'APIRule'). "
            "Must be a valid Kyma resource kind available in the cluster."
        )

    @tool(args_schema=KymaQueryArgs)
    async def kyma_query_tool(uri: str) -> dict | list[dict]:
        """Query the state of Kyma resources in the cluster using the provided URI.
        The URI must follow the format of Kubernetes API.
        Use this to get information about Kyma-specific resources like Function, APIRule, etc.
        Example URIs:
        - /apis/serverless.kyma-project.io/v1alpha2/namespaces/default/functions
        - /apis/gateway.kyma-project.io/v2/namespaces/default/apirules"""
        try:
            return await k8s_client.execute_get_api_request(uri)
        except K8sClientError as e:
            if not e.tool_name:
                e.tool_name = "kyma_query_tool"
            raise
        except Exception as e:
            raise K8sClientError.from_exception(
                exception=e,
                tool_name="kyma_query_tool",
                uri=uri,
            ) from e

    @tool(args_schema=KymaResourceVersionArgs)
    def fetch_kyma_resource_version(resource_kind: str) -> str:
        """Tool for fetching the resource version for a given resource kind.
        Use this to get the resource version for a given resource kind.
        Example resource kinds: Function, APIRule, TracePipeline, etc.
        Use this tool when the resource version is not known or needs
        to be verified or kyma_query_tool returns 404 not found."""
        try:
            version = k8s_client.get_resource_version(resource_kind)
            if version in DEPRECATED_API_VERSIONS:
                _, warning = DEPRECATED_API_VERSIONS[version]
                return f"{version}\nWARNING: {warning}"
            return version
        except Exception as e:
            raise K8sClientError.from_exception(
                exception=e,
                tool_name="fetch_kyma_resource_version",
            ) from e

    return [fetch_kyma_resource_version, kyma_query_tool]


class KymaReActAgent:
    """Stateless ReAct agent using the same tools and prompts as KymaAgent.

    Unlike the graph-based KymaAgent this class:
    - Requires no LangGraph state, supervisor, or subgraph wiring
    - Accepts a query string and returns a string answer directly
    - Supports optional multi-turn chat_history
    """

    def __init__(
        self,
        models: dict[str, IModel | Embeddings],
        k8s_client: IK8sClient,
    ) -> None:
        search_kyma_doc_tool = SearchKymaDocTool(models)
        tools: list[BaseTool] = [*_make_bound_tools(k8s_client), search_kyma_doc_tool]

        llm: BaseChatModel = models["main_model"]  # type: ignore[assignment]
        self._graph = create_agent(
            model=llm,
            tools=tools,
            system_prompt=SystemMessage(content=SYSTEM_PROMPT),
        )

    async def ainvoke(
        self,
        query: str,
        chat_history: list[BaseMessage] | None = None,
    ) -> str:
        """Run the ReAct loop and return the final answer as a string."""
        messages = [*(chat_history or []), HumanMessage(content=query)]
        payload: Any = {"messages": messages}
        result = await self._graph.ainvoke(payload)
        last = result["messages"][-1]
        return str(last.content)
