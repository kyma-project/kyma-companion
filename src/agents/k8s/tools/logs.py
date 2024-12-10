from typing import Annotated

from pydantic import BaseModel
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from services.k8s import IK8sClient

POD_LOGS_TAIL_LINES_LIMIT: int = 10


class FetchPodLogsArgs(BaseModel):
    """Arguments for the fetch_pod_logs tool."""

    name: str
    namespace: str
    container_name: str
    is_terminated: bool
    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")]

    class Config:
        arbitrary_types_allowed = True


@tool(infer_schema=False, args_schema=FetchPodLogsArgs)
def fetch_pod_logs_tool(
    name: str,
    namespace: str,
    container_name: str,
    is_terminated: bool,
    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")],
) -> list[str]:
    """Fetch logs of Kubernetes Pod. Provide is_terminated as true if the pod is not running.
    The logs of previous terminated pod will be fetched."""
    try:
        return k8s_client.fetch_pod_logs(
            name, namespace, container_name, is_terminated, POD_LOGS_TAIL_LINES_LIMIT
        )
    except Exception as e:
        raise Exception(
            f"failed executing fetch_pod_logs for pod: {name} in namespace: {namespace} with "
            f"container: {container_name}, raised the following error: {e}"
        ) from e
