import json
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage
from langgraph.prebuilt import ToolNode

from agents.k8s.tools.logs import POD_LOGS_TAIL_LINES_LIMIT, fetch_pod_logs_tool
from services.k8s import IK8sClient


@pytest.mark.parametrize(
    "given_name, given_namespace, given_container_name, given_error, expected_logs_dict, expected_error",
    [
        # Test case: successful query for logs.
        # Note: expected_logs_dict should match the serialized output (model_dump())
        (
            "my-pod",
            "my-namespace",
            "my-container",
            None,
            {
                "logs": {
                    "current_pod": "line 1\nline 2\nline 3",
                    "previous_pod": "Not available (container has not been restarted)",
                },
                "diagnostic_context": None,
            },
            None,
        ),
        # Test case: exception raised during the query for logs.
        (
            "my-pod",
            "my-namespace",
            "my-container",
            Exception("dummy error 1"),
            None,
            Exception(
                "Error: failed executing fetch_pod_logs_tool, "
                "raised the following error: dummy error 1\n Please fix your mistakes."
            ),
        ),
    ],
)
@pytest.mark.asyncio
async def test_fetch_pod_logs_tool(
    given_name,
    given_namespace,
    given_container_name,
    given_error,
    expected_logs_dict,
    expected_error,
):
    # Given
    tool_node = ToolNode([fetch_pod_logs_tool])
    k8s_client = AsyncMock(spec=IK8sClient)
    if given_error:
        k8s_client.fetch_pod_logs.side_effect = given_error
    else:
        # Mock should return a PodLogsResult Pydantic model, not a dict
        from services.k8s_models import PodLogs, PodLogsResult

        k8s_client.fetch_pod_logs.return_value = PodLogsResult(
            logs=PodLogs(
                current_pod=expected_logs_dict["logs"]["current_pod"],
                previous_pod=expected_logs_dict["logs"]["previous_pod"],
            ),
            diagnostic_context=expected_logs_dict["diagnostic_context"],
        )

    # When: invoke the tool.
    result = await tool_node.ainvoke(
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
        POD_LOGS_TAIL_LINES_LIMIT,
    )
    # check the response.
    if expected_error:
        got_err_msg = result["messages"][0].content
        expected_err_msg = str(expected_error)
        assert got_err_msg == expected_err_msg
    elif expected_logs_dict:
        # The tool node serializes Pydantic models to JSON
        got_obj = json.loads(result["messages"][0].content)
        assert got_obj == expected_logs_dict
