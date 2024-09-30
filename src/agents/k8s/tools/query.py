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
    """Fetch resource data from kubernetes cluster."""
    ## TODO: Add a better description for this tool.
    try:
        result = k8s_client.execute_get_api_request(uri)
        if not isinstance(result, list) and not isinstance(result, dict):
            err_message = (
                f"failed executing k8s_query_tool with URI:\n\n{uri}\n\n"
                f"The result is not a list or dict, but a {type(result)}"
            )
            return {
                "error": err_message,
            }

        return DataSanitizer.sanitize(result)
    except Exception as e:
        err_message = (
            f"failed executing k8s_query_tool with URI:\n\n{uri}\n\n"
            f"raised the following error:\n\n{type(e)}: {e}"
        )
        return {
            "error": err_message,
        }
