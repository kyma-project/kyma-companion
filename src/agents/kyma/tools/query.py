from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict

from services.k8s import IK8sClient
from utils.exceptions import K8sClientError


class ClusterQueryToolArgs(BaseModel):
    """Arguments for the cluster_query_tool."""

    uri: str = Field(
        description="Kubernetes API URI path for querying Kyma and Kubernetes resources. "
        "Must follow the format of Kubernetes API paths like "
        "'/apis/serverless.kyma-project.io/v1alpha2/namespaces/default/functions' "
        "or '/api/v1/namespaces/default/pods'."
    )
    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")]

    # Model configuration for Pydantic.
    model_config = ConfigDict(arbitrary_types_allowed=True)


@tool(infer_schema=False, args_schema=ClusterQueryToolArgs)
async def cluster_query_tool(
    uri: str, k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")]
) -> dict | list[dict]:
    """Query the state of Kyma and Kubernetes resources in the cluster using the provided URI.
    The URI must follow the format of Kubernetes API.
    Use this for both Kyma-specific resources (Function, APIRule, etc.) and
    generic Kubernetes resources (Pod, Deployment, Service, etc.).
    Example URIs:
    - /apis/serverless.kyma-project.io/v1alpha2/namespaces/default/functions
    - /api/v1/namespaces/default/pods
    - /apis/apps/v1/namespaces/default/deployments"""
    try:
        return await k8s_client.execute_get_api_request(uri)
    except K8sClientError as e:
        if not e.tool_name:
            e.tool_name = "cluster_query_tool"
        raise
    except Exception as e:
        raise K8sClientError.from_exception(
            exception=e,
            tool_name="cluster_query_tool",
            uri=uri,
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


DEPRECATED_API_VERSIONS = {
    "gateway.kyma-project.io/v1beta1": (
        "gateway.kyma-project.io/v2",
        "APIRule v1beta1 is deprecated and removed in API Gateway module release 3.4. "
        "Migrate to v2. See: https://kyma-project.io/#/api-gateway/user/custom-resources/apirule/04-10-apirule-custom-resource",
    ),
}


@tool(infer_schema=False, args_schema=KymaResourceVersionToolArgs)
def fetch_kyma_resource_version(
    resource_kind: str,
    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")],
) -> str:
    """Tool for fetching the resource version for a given resource kind.
    Use this to get the resource version for a given resource kind.
    Example resource kinds: Function, APIRule, TracePipeline, etc.
    Use this tool when the resource version is not known or needs
    to be verified or cluster_query_tool returns 404 not found.
    """
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
