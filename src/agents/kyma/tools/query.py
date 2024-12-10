from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel

from services.k8s import DataSanitizer, IK8sClient


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
        response = k8s_client.execute_get_api_request(uri)
        result = response.json()
        if not isinstance(result, list) and not isinstance(result, dict):
            raise Exception(
                f"failed executing kyma_query_tool with URI: {uri}."
                f"The result is not a list or dict, but a {type(result)}"
            )

        return DataSanitizer.sanitize(result)
    except Exception as e:
        raise Exception(
            f"failed executing kyma_query_tool with URI: {uri},"
            f"raised the following error: {e}"
        ) from e
