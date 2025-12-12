import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from langchain_core.messages import AIMessage
from langgraph.prebuilt import ToolNode

from agents.common.data import Message
from agents.k8s.tools.query import k8s_overview_query_tool, k8s_query_tool
from services.k8s import IK8sClient


def sample_k8s_secret():
    return {
        "kind": "Secret",
        "apiVersion": "v1",
        "metadata": {
            "name": "my-secret",
        },
        "data": {
            "config": "this is a test config",
        },
    }


def sample_k8s_sanitized_secret():
    return {
        "kind": "Secret",
        "apiVersion": "v1",
        "metadata": {
            "name": "my-secret",
        },
        "data": {},
    }


@pytest.mark.parametrize(
    "given_uri, given_object, given_exception, expected_object, expected_error",
    [
        # # Test case: successful query for secret object. The data should be sanitized.
        (
            "v1/secret/my-secret",
            sample_k8s_secret(),
            None,
            sample_k8s_secret(),
            None,
        ),
        # Test case: the execute_get_api_request returns an exception.
        (
            "v1/secret/my-secret",
            sample_k8s_secret(),
            Exception("dummy error 1"),
            None,
            Exception(
                "Error: failed executing k8s_query_tool with URI: v1/secret/my-secret,raised the following error: dummy error 1\n Please fix your mistakes."
            ),
        ),
        # Test case: the execute_get_api_request returns not a dict or list.
        (
            "v1/secret/my-secret",
            "not a dict or list",
            None,
            None,
            Exception(
                "Error: failed executing k8s_query_tool with URI: v1/secret/my-secret,raised the following error: Invalid result type: <class 'str'>\n Please fix your mistakes."
            ),
        ),
    ],
)
@pytest.mark.asyncio
async def test_k8s_query_tool(
    given_uri, given_object, given_exception, expected_object, expected_error
):
    # Given
    tool_node = ToolNode([k8s_query_tool])
    k8s_client = AsyncMock(spec=IK8sClient)
    if given_exception:
        k8s_client.execute_get_api_request.side_effect = given_exception
    else:
        k8s_client.execute_get_api_request.return_value = given_object

    # When: invoke the tool.
    result = await tool_node.ainvoke(
        {
            "k8s_client": k8s_client,
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "k8s_query_tool",
                            "args": {"uri": given_uri},
                            "id": "id1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ],
        }
    )

    # Then
    # check if the method was called with the given URI.
    k8s_client.execute_get_api_request.assert_called_once_with(given_uri)
    # check the response.
    if expected_error:
        got_err_msg = result["messages"][0].content
        expected_err_msg = str(expected_error)
        assert got_err_msg == expected_err_msg
    elif expected_object:
        got_obj = json.loads(result["messages"][0].content)
        assert got_obj == expected_object


def sample_cluster_overview():
    return {"nodes": 3, "namespaces": ["default", "kube-system"], "version": "v1.25.0"}


def sample_namespace_overview():
    return {"pods": 5, "services": 2, "deployments": 3}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "given_namespace, given_resource_kind, given_result, given_exception, expected_result, expected_error",
    [
        # Test case: successful cluster overview
        (
            "",
            "cluster",
            sample_cluster_overview(),
            None,
            sample_cluster_overview(),
            None,
        ),
        # Test case: successful namespace overview
        (
            "default",
            "namespace",
            sample_namespace_overview(),
            None,
            sample_namespace_overview(),
            None,
        ),
        # Test case: exception during execution
        (
            "default",
            "namespace",
            None,
            Exception("cluster unavailable"),
            None,
            Exception(
                "Error: Exception('cluster unavailable')\n Please fix your mistakes."
            ),
        ),
        # Test case: invalid resource kind
        (
            "default",
            "invalid_kind",
            None,
            Exception("Unsupported resource kind: invalid_kind"),
            None,
            Exception(
                "Error: Exception('Unsupported resource kind: invalid_kind')\n Please fix your mistakes."
            ),
        ),
    ],
)
@patch("agents.k8s.tools.query.get_relevant_context_from_k8s_cluster")
async def test_k8s_overview_query_tool(
    mock_get_context,
    given_namespace,
    given_resource_kind,
    given_result,
    given_exception,
    expected_result,
    expected_error,
):
    # Given
    tool_node = ToolNode([k8s_overview_query_tool])
    k8s_client = Mock(spec=IK8sClient)

    # Configure the mock
    if given_exception:
        mock_get_context.side_effect = given_exception
    else:
        mock_get_context.return_value = given_result

    # When: invoke the tool.
    result = await tool_node.ainvoke(
        {
            "k8s_client": k8s_client,
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "k8s_overview_query_tool",
                            "args": {
                                "namespace": given_namespace,
                                "resource_kind": given_resource_kind,
                            },
                            "id": "id1",
                            "type": "tool_call",
                        }
                    ],
                ),
            ],
        }
    )

    # Then
    if expected_error:
        got_err_msg = result["messages"][0].content
        expected_err_msg = str(expected_error)
        assert got_err_msg == expected_err_msg
    elif expected_result:
        got_obj = json.loads(result["messages"][0].content)
        assert got_obj == expected_result

    # Verify the mock was called correctly
    mock_get_context.assert_called_once_with(
        Message(
            resource_kind=given_resource_kind,
            namespace=given_namespace,
            query="",
            resource_api_version="",
            resource_name="",
        ),
        k8s_client,
    )
