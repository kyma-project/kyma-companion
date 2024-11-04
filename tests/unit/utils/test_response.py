from unittest.mock import Mock, patch

import pytest

from utils.response import prepare_chunk_response


@pytest.mark.parametrize(
    "input, expected",
    [
        (
            # input
            b'{"Planner": {"messages": [{"content": "Task decomposed into subtasks and assigned '
            b'to agents: [{\\"description\\": \\"Create a Hello World Python Serverless '
            b'Function in Kyma.\\", \\"assigned_to\\": \\"KymaAgent\\", \\"status\\": '
            b'\\"pending\\", \\"result\\": null}, {\\"description\\": \\"Create an API '
            b'Rule to expose the Python Serverless Function externally.\\", \\"assigned_to\\": '
            b'\\"KymaAgent\\", \\"status\\": \\"pending\\", \\"result\\": null}]", "additional_kwargs": {}, '
            b'"response_metadata": {}, "type": "ai", "name": "Planner", "id": null, "example": false, '
            b'"tool_calls": [], "invalid_tool_calls": [], "usage_metadata": null}], "next": "Continue", '
            b'"subtasks": [{"description": "Create a Hello World Python Serverless Function in Kyma.", '
            b'"assigned_to": "KymaAgent", "status": "pending", "result": null}, {"description": '
            b'"Create an API Rule to expose the Python Serverless Function externally.", "assigned_to": '
            b'"KymaAgent", "status": "pending", "result": null}], "final_response": null, "error": null}}',
            # expected
            b'{"event": "agent_action", "data": {"agent": "Planner", "answer": {"content": '
            b'"Task decomposed into subtasks and assigned to agents: [{\\"description\\": '
            b'\\"Create a Hello World Python Serverless Function in Kyma.\\", \\"assigned_to\\": '
            b'\\"KymaAgent\\", \\"status\\": \\"pending\\", \\"result\\": null}, {\\"description\\": '
            b'\\"Create an API Rule to expose the Python Serverless Function externally.\\", '
            b'\\"assigned_to\\": \\"KymaAgent\\", \\"status\\": \\"pending\\", \\"result\\": null}]", '
            b'"subtasks": [{"description": "Create a Hello World Python Serverless '
            b'Function in Kyma.", "assigned_to": "KymaAgent", "status": "pending", '
            b'"result": null}, {"description": "Create an API Rule to expose the Python '
            b'Serverless Function externally.", "assigned_to": "KymaAgent", "status": "pending", '
            b'"result": null}]}}}',
        ),
        (
            # input
            b'{"Supervisor": {"messages": [{"content": "{\\n  \\"next\\": \\"KymaAgent\\"\\n}", '
            b'"additional_kwargs": {}, "response_metadata": {}, "type": "ai", "name": "Supervisor", '
            b'"id": null, "example": false, "tool_calls": [], "invalid_tool_calls": [], "usage_metadata": null}], '
            b'"next": "KymaAgent", "subtasks": '
            b'[{"description": "Create a Hello World Python Serverless Function in Kyma.", "assigned_to": '
            b'"KymaAgent", "status": "pending", "result": null}, {"description": '
            b'"Create an API Rule to expose the Python Serverless Function externally.", '
            b'"assigned_to": "KymaAgent", "status": "pending", "result": null}]}}',
            # expected
            b'{"event": "agent_action", "data": {"agent": "Supervisor", "answer": '
            b'{"content": "{\\n  \\"next\\": \\"KymaAgent\\"\\n}", '
            b'"next": "KymaAgent"}}}',
        ),
        (
            # input
            b'{"KymaAgent": {"messages": [{"content": "To create an API Rule in Kyma to '
            b'expose a service externally", "additional_kwargs": {}, "response_metadata": {}, '
            b'"type": "ai", "name": "Supervisor", "id": null, "example": false, "tool_calls": [], '
            b'"invalid_tool_calls": [], "usage_metadata": null}]}}',
            # expected
            b'{"event": "agent_action", "data": {"agent": "KymaAgent", "answer": {"content": '
            b'"To create an API Rule in Kyma to expose a service externally"}}}',
        ),
        (
            # input
            b'{"KubernetesAgent": {"messages": [{"content": "To create a kubernetes deployment", '
            b'"additional_kwargs": {}, "response_metadata": {}, "type": "ai", "name": "Supervisor", '
            b'"id": null, "example": false, "tool_calls": [], "invalid_tool_calls": [], "usage_metadata": null}]}}',
            # expected
            b'{"event": "agent_action", "data": {"agent": "KubernetesAgent", '
            b'"answer": {"content": "To create a kubernetes deployment"}}}',
        ),
        (
            # input
            b'{"KubernetesAgent": {"error": "Error occurred"}}',
            # expected
            b'{"event": "agent_action", "data": {"agent": "KubernetesAgent", "error": "Error occurred"}}',
        ),
        (
            # input
            b'{"InvalidJSON"',
            # expected
            b'{"event": "unknown", "data": {"error": "Invalid JSON"}}',
        ),
        (
            # input
            b"{}",
            # expected
            b'{"event": "unknown", "data": {"error": "No agent found"}}',
        ),
    ],
)
@patch("utils.response.get_logger", Mock())
def test_prepare_chunk_response(input, expected):
    assert prepare_chunk_response(input) == expected
