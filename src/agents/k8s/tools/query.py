from typing import Annotated

from kubernetes.client.exceptions import ApiException
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel
from pydantic.config import ConfigDict

from agents.common.data import Message
from agents.common.utils import (
    get_relevant_context_from_k8s_cluster,
)
from services.k8s import IK8sClient, K8sClientError


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
        if not isinstance(result, (list, dict)):
            raise K8sClientError(
                message=f"Invalid result type: {type(result)}",
                status_code=500,
                uri=uri,
                tool_name="k8s_query_tool",
            )
        return result
    except K8sClientError as e:
        if not e.tool_name:
            e.tool_name = "k8s_query_tool"
        raise
    except ApiException as e:
        # Preserve ApiException status code in K8sClientError
        raise K8sClientError(
            message=str(e),
            status_code=e.status,
            uri=uri,
            tool_name="k8s_query_tool",
        ) from e
    except Exception as e:
        raise K8sClientError(
            message=str(e),
            status_code=getattr(e, "status_code", 500),
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
