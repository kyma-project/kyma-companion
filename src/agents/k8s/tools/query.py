from http import HTTPStatus
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel
from pydantic.config import ConfigDict

from agents.common.data import Message
from agents.common.utils import (
    get_relevant_context_from_k8s_cluster,
)
from services.k8s import IK8sClient
from utils.exceptions import K8sClientError


class K8sQueryToolArgs(BaseModel):
    """Arguments for the k8s_query_tool tool."""

    uri: str
    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")]

    # Model configuration for Pydantic.
    model_config = ConfigDict(arbitrary_types_allowed=True)


@tool(infer_schema=False, args_schema=K8sQueryToolArgs)
async def k8s_query_tool(
    uri: str, k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")]
) -> dict | list[dict]:
    """Query the state of objects in Kubernetes using the provided URI.
    The URI must follow the format of Kubernetes API.
    The returned data is sanitized to remove any sensitive information.
    For example, it will always remove the `data` field of a `Secret` object."""
    try:
        result = await k8s_client.execute_get_api_request(uri)
        return result
    except K8sClientError as e:
        # Add tool name if not already set
        if not e.tool_name:
            e.tool_name = "k8s_query_tool"
        raise
    except Exception as e:
        # Extract status code if available (e.g., from ApiException)
        # HTTPStatus members are ints, so we can safely use the value
        status_code: int = (
            e.status
            if hasattr(e, "status") and isinstance(e.status, int)
            else HTTPStatus.INTERNAL_SERVER_ERROR
        )

        raise K8sClientError(
            message=str(e),
            status_code=status_code,
            uri=uri,
            tool_name="k8s_query_tool",
        ) from e


@tool()
async def k8s_overview_query_tool(
    namespace: str,
    resource_kind: str,
    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")],
) -> str:
    """Tool for fetching relevant context data from a Kubernetes cluster.
    To get an overview of cluster - use namespace - "" , resource_kind - "cluster".
    To get an overview of namespace - provide namespace and resource_kind - "namespace".
    """
    message = Message(
        resource_kind=resource_kind,
        namespace=namespace,
        query="",
        resource_api_version="",
        resource_name="",
    )
    return await get_relevant_context_from_k8s_cluster(message, k8s_client)
