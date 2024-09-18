# write test that tests the prepare_response_chunk function
from unittest.mock import Mock, patch

import pytest

from utils.response import prepare_chunk_response


@pytest.mark.parametrize(
    "chunk, expected",
    [
        (
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
            b'{"event": "agent_action", "data": {"agent": "Planner", "answer": {"messages": [{"content": '
            b'"Task decomposed into subtasks and assigned to agents: [{\\"description\\": '
            b'\\"Create a Hello World Python Serverless Function in Kyma.\\", \\"assigned_to\\": '
            b'\\"KymaAgent\\", \\"status\\": \\"pending\\", \\"result\\": null}, {\\"description\\": '
            b'\\"Create an API Rule to expose the Python Serverless Function externally.\\", '
            b'\\"assigned_to\\": \\"KymaAgent\\", \\"status\\": \\"pending\\", \\"result\\": null}]"}], '
            b'"next": "Continue", "subtasks": [{"description": "Create a Hello World Python Serverless '
            b'Function in Kyma.", "assigned_to": "KymaAgent", "status": "pending", '
            b'"result": null}, {"description": "Create an API Rule to expose the Python '
            b'Serverless Function externally.", "assigned_to": "KymaAgent", "status": "pending", '
            b'"result": null}], "final_response": null, "error": null}}}',
        ),
        (
            b'{"Supervisor": {"messages": [{"content": "{\\n  \\"next\\": \\"KymaAgent\\"\\n}", '
            b'"additional_kwargs": {}, "response_metadata": {}, "type": "ai", "name": "Supervisor", '
            b'"id": null, "example": false, "tool_calls": [], "invalid_tool_calls": [], "usage_metadata": null}], '
            b'"next": "KymaAgent", "subtasks": '
            b'[{"description": "Create a Hello World Python Serverless Function in Kyma.", "assigned_to": '
            b'"KymaAgent", "status": "pending", "result": null}, {"description": '
            b'"Create an API Rule to expose the Python Serverless Function externally.", '
            b'"assigned_to": "KymaAgent", "status": "pending", "result": null}]}}',
            b'{"event": "agent_action", "data": {"agent": "Supervisor", "answer": '
            b'{"messages": [{"content": "{\\n  \\"next\\": \\"KymaAgent\\"\\n}"}], '
            b'"next": "KymaAgent", "subtasks": [{"description": '
            b'"Create a Hello World Python Serverless Function in Kyma.", "assigned_to": "KymaAgent", '
            b'"status": "pending", "result": null}, {"description": "Create an API Rule to expose '
            b'the Python Serverless Function externally.", "assigned_to": "KymaAgent", "status": "pending", '
            b'"result": null}]}}}',
        ),
        (
            b'{"KymaAgent": {"messages": [{"content": "To create an API Rule in Kyma to '
            b'expose a service externally", "additional_kwargs": {}, "response_metadata": {}, '
            b'"type": "ai", "name": "Supervisor", "id": null, "example": false, "tool_calls": [], '
            b'"invalid_tool_calls": [], "usage_metadata": null}]}}',
            b'{"event": "agent_action", "data": {"agent": "KymaAgent", "answer": {"messages": '
            b'[{"content": "To create an API Rule in Kyma to expose a service externally"}]}}}',
        ),
        (
            b'{"KubernetesAgent": {"messages": [{"content": "To create a kubernetes deployment", '
            b'"additional_kwargs": {}, "response_metadata": {}, "type": "ai", "name": "Supervisor", '
            b'"id": null, "example": false, "tool_calls": [], "invalid_tool_calls": [], "usage_metadata": null}]}}',
            b'{"event": "agent_action", "data": {"agent": "KubernetesAgent", '
            b'"answer": {"messages": [{"content": "To create a kubernetes deployment"}]}}}',
        ),
        (
            b'{"Exit": {"next": "__end__", "final_response": '
            b'"To create a Kubernetes application and expose it when deployed in the Kyma runtime"}}',
            b'{"event": "final_response", "data": {"answer": "To create a Kubernetes application and expose '
            b'it when deployed in the Kyma runtime"}}',
        ),
        (
            b'{"InvalidJSON"',
            b'{"event": "error", "data": {"message": "Invalid JSON"}}',
        ),
        (
            b"{}",
            b'{"event": "error", "data": {"message": "No agent found"}}',
        ),
    ],
)
@patch("utils.response.get_logger", Mock())
def test_prepare_chunk_response(chunk, expected):
    assert prepare_chunk_response(chunk) == expected
