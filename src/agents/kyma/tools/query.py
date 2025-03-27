from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel

from agents.common.utils import filter_kyma_data
from services.k8s import IK8sClient


class KymaQueryToolArgs(BaseModel):
    """Arguments for the kyma_query_tool."""

    uri: str
    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")]

    class Config:
        arbitrary_types_allowed = True


@tool(infer_schema=False, args_schema=KymaQueryToolArgs)
def kyma_query_tool(
    uri: str, k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")]
) -> dict | list[dict]:
    """Query the state of Kyma resources in the cluster using the provided URI.
    The URI must follow the format of Kubernetes API.
    Use this to get information about Kyma-specific resources like Function, APIRule, etc.
    Example URIs:
    - /apis/serverless.kyma-project.io/v1alpha2/namespaces/default/functions
    - /apis/gateway.kyma-project.io/v1beta1/namespaces/default/apirules"""
    try:
        result = k8s_client.execute_get_api_request(uri)

        if result.get("items"):
            # Filter out undesired fields from result
            result["items"] = [
                filtered
                for kyma_data in result.get("items", [])
                if (filtered := filter_kyma_data(kyma_data)) is not None
            ]

        if not isinstance(result, list) and not isinstance(result, dict):
            raise Exception(
                f"failed executing kyma_query_tool with URI: {uri}."
                f"The result is not a list or dict, but a {type(result)}"
            )

        return result
    except Exception as e:
        raise Exception(
            f"failed executing kyma_query_tool with URI: {uri},"
            f"raised the following error: {e}"
        ) from e
