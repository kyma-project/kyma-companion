from langchain_core.tools import tool
from typing_extensions import Annotated
from langgraph.prebuilt import InjectedState
from services.k8s import IK8sClient, DataSanitizer

from langchain_core.pydantic_v1 import BaseModel
from services.k8s import IK8sClient

class K8sQueryToolArgs(BaseModel):
    uri: str
    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")]

    class Config:
        arbitrary_types_allowed = True

@tool(infer_schema=False, args_schema=K8sQueryToolArgs)
def k8s_query_tool(uri: str, k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")]):
    """Fetch resource data from kubernetes cluster."""
    ## TODO: Add a better description for this tool.
    try:
        result = k8s_client.execute_get_api_request(uri)
        if not isinstance(result, list) and not isinstance(result, dict):
            return f"failed executing k8s_query_tool with URI:\n\n{uri}\n\nThe result is not a list or dict, but a {type(result)}"

        return DataSanitizer.sanitize(result)
    except Exception as e:
        return f"failed executing k8s_query_tool with URI:\n\n{uri}\n\nraised the following error:\n\n{type(e)}: {e}"