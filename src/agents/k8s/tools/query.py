from typing import Annotated

from langchain_core.pydantic_v1 import BaseModel
from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from services.k8s import DataSanitizer, IK8sClient


class K8sQueryToolArgs(BaseModel):
    """Arguments for the k8s_query_tool tool."""

    uri: str
    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")]

    class Config:
        arbitrary_types_allowed = True


@tool(infer_schema=False, args_schema=K8sQueryToolArgs)
def k8s_query_tool(
    uri: str, k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")]
) -> dict | list[dict]:
    """Query the state of objects in Kubernetes using the provided URI.
    The URI must follow the format of Kubernetes API.
    The returned data is sanitized to remove any sensitive information.
    For example, it will always remove the `data` field of a `Secret` object."""
    try:
        response = k8s_client.execute_get_api_request(uri)
        result = response.json()
        if not isinstance(result, list) and not isinstance(result, dict):
            raise Exception(
                f"failed executing k8s_query_tool with URI: {uri}."
                f"The result is not a list or dict, but a {type(result)}"
            )

        return DataSanitizer.sanitize(result)
    except Exception as e:
        raise Exception(
            f"failed executing k8s_query_tool with URI: {uri},"
            f"raised the following error: {e}"
        ) from e
