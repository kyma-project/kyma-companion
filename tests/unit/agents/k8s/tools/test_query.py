import json
from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage
from langgraph.prebuilt import ToolNode

from agents.k8s.tools.query import k8s_query_tool
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
            sample_k8s_sanitized_secret(),
            None,
        ),
        # Test case: the execute_get_api_request returns an exception.
        (
            "v1/secret/my-secret",
            sample_k8s_secret(),
            Exception("dummy error 1"),
            None,
            Exception(
                "Error: Exception('failed executing k8s_query_tool with URI: v1/secret/my-secret,"
                "raised the following error: dummy error 1')\n Please fix your mistakes."
            ),
        ),
        # Test case: the execute_get_api_request returns not a dict or list.
        (
            "v1/secret/my-secret",
            "not a dict or list",
            None,
            None,
            Exception(
                'Error: Exception("failed executing k8s_query_tool with URI: v1/secret/my-secret,'
                "raised the following error: failed executing k8s_query_tool with URI: v1/secret/my-secret."
                "The result is not a list or dict, but a <class 'str'>\")\n Please fix your mistakes."
            ),
        ),
    ],
)
def test_k8s_query_tool(
    given_uri, given_object, given_exception, expected_object, expected_error
):
    # Given
    tool_node = ToolNode([k8s_query_tool])
    k8s_client = Mock(spec=IK8sClient)
    if given_exception:
        k8s_client.execute_get_api_request.side_effect = given_exception
    else:
        k8s_client.execute_get_api_request.return_value.json.return_value = given_object

    # When: invoke the tool.
    result = tool_node.invoke(
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
