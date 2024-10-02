import json
from unittest.mock import Mock

import pytest
from langchain_core.messages import AIMessage
from langgraph.prebuilt import ToolNode

from agents.k8s.tools.logs import POD_LOGS_TAIL_LINES_LIMIT, fetch_pod_logs_tool
from services.k8s import IK8sClient


@pytest.mark.parametrize(
    "given_name, given_namespace, given_container_name, "
    "given_is_terminated, given_error, expected_logs, expected_error",
    [
        # Test case: successful query for logs.
        (
            "my-pod",
            "my-namespace",
            "my-container",
            False,
            None,
            ["line 1", "line 2", "line 3"],
            None,
        ),
        # Test case: exception raised during the query for logs.
        (
            "my-pod",
            "my-namespace",
            "my-container",
            False,
            Exception("dummy error 1"),
            None,
            Exception(
                "Error: Exception('failed executing fetch_pod_logs for pod: my-pod in namespace: my-namespace "
                "with container: my-container, raised the following error: dummy error 1')\n Please fix your mistakes."
            ),
        ),
    ],
)
def test_fetch_pod_logs_tool(
    given_name,
    given_namespace,
    given_container_name,
    given_is_terminated,
    given_error,
    expected_logs,
    expected_error,
):
    # Given
    tool_node = ToolNode([fetch_pod_logs_tool])
    k8s_client = Mock(spec=IK8sClient)
    if given_error:
        k8s_client.fetch_pod_logs.side_effect = given_error
    else:
        k8s_client.fetch_pod_logs.return_value = expected_logs

    # When: invoke the tool.
    result = tool_node.invoke(
        {
            "k8s_client": k8s_client,
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "fetch_pod_logs_tool",
                            "args": {
                                "name": given_name,
                                "namespace": given_namespace,
                                "container_name": given_container_name,
                                "is_terminated": given_is_terminated,
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
    # check if the method was called with the given URI.
    k8s_client.fetch_pod_logs.assert_called_once_with(
        given_name,
        given_namespace,
        given_container_name,
        given_is_terminated,
        POD_LOGS_TAIL_LINES_LIMIT,
    )
    # check the response.
    if expected_error:
        got_err_msg = result["messages"][0].content
        expected_err_msg = str(expected_error)
        assert got_err_msg == expected_err_msg
    elif expected_logs:
        got_obj = json.loads(result["messages"][0].content)
        assert got_obj == expected_logs
