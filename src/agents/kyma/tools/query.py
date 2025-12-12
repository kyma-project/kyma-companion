from http import HTTPStatus
from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict

from services.k8s import IK8sClient
from utils.exceptions import K8sClientError


class KymaQueryToolArgs(BaseModel):
    """Arguments for the kyma_query_tool."""

    uri: str = Field(
        description="Kubernetes API URI path for querying Kyma resources. "
        "Must follow the format of Kubernetes API paths like "
        "'/apis/serverless.kyma-project.io/v1alpha2/namespaces/default/functions'."
    )
    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")]

    # Model configuration for Pydantic.
    model_config = ConfigDict(arbitrary_types_allowed=True)


@tool(infer_schema=False, args_schema=KymaQueryToolArgs)
async def kyma_query_tool(
    uri: str, k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")]
) -> dict | list[dict]:
    """Query the state of Kyma resources in the cluster using the provided URI.
    The URI must follow the format of Kubernetes API.
    Use this to get information about Kyma-specific resources like Function, APIRule, etc.
    Example URIs:
    - /apis/serverless.kyma-project.io/v1alpha2/namespaces/default/functions
    - /apis/gateway.kyma-project.io/v1beta1/namespaces/default/apirules"""
    try:
        result = await k8s_client.execute_get_api_request(uri)
        return result
    except K8sClientError as e:
        # Add tool name if not already set
        if not e.tool_name:
            e.tool_name = "kyma_query_tool"
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
            tool_name="kyma_query_tool",
        ) from e


class KymaResourceVersionToolArgs(BaseModel):
    """Arguments for the fetch_kyma_resource_version tool."""

    resource_kind: str = Field(
        description="Kind of Kyma resource to get the version for (e.g., 'Function', 'APIRule', 'ServiceInstance'). "
        "Must be a valid Kyma resource kind available in the cluster."
    )

    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")]

    # Model configuration for Pydantic.
    model_config = ConfigDict(arbitrary_types_allowed=True)


@tool(infer_schema=False, args_schema=KymaResourceVersionToolArgs)
def fetch_kyma_resource_version(
    resource_kind: str,
    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")],
) -> str:
    """Tool for fetching the resource version for a given resource kind.
    Use this to get the resource version for a given resource kind.
    Example resource kinds: Function, APIRule, TracePipeline, etc.
    Use this tool when the resource version is not known or needs
    to be verified or kyma_query_tool returns 404 not found.
    """
    try:
        resource_version = k8s_client.get_resource_version(resource_kind)
        return resource_version
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
            tool_name="fetch_kyma_resource_version",
        ) from e
