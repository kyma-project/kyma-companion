from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel
from pydantic.config import ConfigDict

from services.k8s import IK8sClient
from utils.exceptions import K8sClientError, NoLogsAvailableError

POD_LOGS_TAIL_LINES_LIMIT: int = 10


class FetchPodLogsArgs(BaseModel):
    """Arguments for the fetch_pod_logs tool."""

    name: str
    namespace: str
    container_name: str
    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")]

    # Model configuration for Pydantic.
    model_config = ConfigDict(arbitrary_types_allowed=True)


@tool(infer_schema=False, args_schema=FetchPodLogsArgs)
async def fetch_pod_logs_tool(
    name: str,
    namespace: str,
    container_name: str,
    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")],
) -> dict:
    """Fetch logs of Kubernetes Pod. Returns structured response with current and previous logs,
    plus diagnostic context if current logs are unavailable."""
    try:
        result = await k8s_client.fetch_pod_logs(name, namespace, container_name, POD_LOGS_TAIL_LINES_LIMIT)
        # Serialize Pydantic model to dict for langchain tool compatibility
        return result.model_dump(mode="json", by_alias=True)
    except NoLogsAvailableError:
        # Let NoLogsAvailableError pass through - router will handle it
        raise
    except Exception as e:
        raise K8sClientError.from_exception(
            exception=e,
            tool_name="fetch_pod_logs_tool",
        ) from e
