from typing import Annotated, Any

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict

from services.k8s import IK8sClient
from utils.logging import get_logger

logger = get_logger(__name__)


class DiagnoseClusterArgs(BaseModel):
    """Arguments for the diagnose_cluster tool."""

    query: str = Field(
        description="The user's cluster diagnostics query, e.g. "
        "'What is wrong with my cluster?', 'Check cluster health', "
        "'Are there any issues in my cluster?'"
    )
    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")]

    model_config = ConfigDict(arbitrary_types_allowed=True)


class DiagnoseClusterTool(BaseTool):
    """Tool that delegates to the ClusterDiagnosticsAgent sub-agent.

    This wraps the ClusterDiagnosticsAgent's compiled graph as a LangChain tool
    so that the KymaAgent can invoke it like any other tool.
    """

    name: str = "diagnose_cluster"
    description: str = (
        "Run a comprehensive cluster diagnostics check. "
        "Collects cluster warning events, node resource usage and health, "
        "and Kyma module statuses, then produces a structured diagnostic report. "
        "Use this when the user asks about overall cluster health, cluster-wide "
        "troubleshooting, or general cluster problems."
    )
    args_schema: type[BaseModel] = DiagnoseClusterArgs
    diagnostics_agent: Any = None

    def __init__(self, diagnostics_agent: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.diagnostics_agent = diagnostics_agent

    def _run(self, query: str, k8s_client: IK8sClient) -> str:
        raise NotImplementedError("Use async invocation via _arun.")

    async def _arun(
        self,
        query: str,
        k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")],
    ) -> str:
        """Invoke the ClusterDiagnosticsAgent and return its final response."""
        graph = self.diagnostics_agent.agent_node()
        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content=query)],
                "k8s_client": k8s_client,
            }
        )

        messages = result.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, AIMessage) and msg.content:
                return msg.content

        return "Cluster diagnostics completed but produced no output."
