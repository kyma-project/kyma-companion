from typing import Annotated

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState
from pydantic import BaseModel

from agents.common.data import Message
from agents.common.utils import (
    get_relevant_context_from_k8s_cluster,
)
from initial_questions.inital_questions import InitialQuestionsHandler
from services.k8s import IK8sClient
from utils.models.factory import IModel, ModelType


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
        result = k8s_client.execute_get_api_request(uri)
        if not isinstance(result, list) and not isinstance(result, dict):
            raise Exception(
                f"failed executing k8s_query_tool with URI: {uri}."
                f"The result is not a list or dict, but a {type(result)}"
            )

        return result
    except Exception as e:
        raise Exception(
            f"failed executing k8s_query_tool with URI: {uri},"
            f"raised the following error: {e}"
        ) from e


@tool()
def k8s_query_tool_with_filter(
    namespace: str,
    resource_kind: str,
    k8s_client: Annotated[IK8sClient, InjectedState("k8s_client")],
) -> dict | list[dict]:
    """Tool for fetching relevant context data from a Kubernetes cluster.
    To get an overview of cluster - use namespace - "" , resource_kind - "cluster".
    To get an overview of namespace - provide namespace and resource_kind - "namespace".
    """
    try:
        message = Message(
            resource_kind=resource_kind,
            namespace=namespace,
            query="",
            resource_api_version="",
            resource_name="",
        )
        result = get_relevant_context_from_k8s_cluster(message, k8s_client)

        return result
    except Exception as e:
        raise Exception(
            f"failed executing k8s_query_tool with" f"raised the following error: {e}"
        ) from e
