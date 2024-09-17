# write test that tests the prepare_response_chunk function
import pytest

from utils.response import prepare_chunk_response


@pytest.mark.parametrize(
    "chunk, expected",
    [
        (
            b'{"Planner": {"messages": [{"content": "Task decomposed into subtasks and assigned to agents: [{\\"description\\": \\"Create a Hello World Python Serverless Function in Kyma.\\", \\"assigned_to\\": \\"KymaAgent\\", \\"status\\": \\"pending\\", \\"result\\": null}, {\\"description\\": \\"Create an API Rule to expose the Python Serverless Function externally.\\", \\"assigned_to\\": \\"KymaAgent\\", \\"status\\": \\"pending\\", \\"result\\": null}]", "additional_kwargs": {}, "response_metadata": {}, "type": "ai", "name": "Planner", "id": null, "example": false, "tool_calls": [], "invalid_tool_calls": [], "usage_metadata": null}], "next": "Continue", "subtasks": [{"description": "Create a Hello World Python Serverless Function in Kyma.", "assigned_to": "KymaAgent", "status": "pending", "result": null}, {"description": "Create an API Rule to expose the Python Serverless Function externally.", "assigned_to": "KymaAgent", "status": "pending", "result": null}], "final_response": null, "error": null}}',
            b'{"event": "agent_action", "data": {"agent": "Planner", "answer": {"messages": [{"content": "Task decomposed into subtasks and assigned to agents: [{\\"description\\": \\"Create a Hello World Python Serverless Function in Kyma.\\", \\"assigned_to\\": \\"KymaAgent\\", \\"status\\": \\"pending\\", \\"result\\": null}, {\\"description\\": \\"Create an API Rule to expose the Python Serverless Function externally.\\", \\"assigned_to\\": \\"KymaAgent\\", \\"status\\": \\"pending\\", \\"result\\": null}]", "additional_kwargs": {}, "response_metadata": {}, "type": "ai", "name": "Planner", "id": null, "example": false, "tool_calls": [], "invalid_tool_calls": [], "usage_metadata": null}], "next": "Continue", "subtasks": [{"description": "Create a Hello World Python Serverless Function in Kyma.", "assigned_to": "KymaAgent", "status": "pending", "result": null}, {"description": "Create an API Rule to expose the Python Serverless Function externally.", "assigned_to": "KymaAgent", "status": "pending", "result": null}], "final_response": null, "error": null}}}',
        ),
        (
            b'{"Supervisor": {"messages": [{"content": "{\\n  \\"next\\": \\"KymaAgent\\"\\n}", "additional_kwargs": {}, "response_metadata": {}, "type": "ai", "name": "Supervisor", "id": null, "example": false, "tool_calls": [], "invalid_tool_calls": [], "usage_metadata": null}], "next": "KymaAgent", "subtasks": [{"description": "Create a Hello World Python Serverless Function in Kyma.", "assigned_to": "KymaAgent", "status": "pending", "result": null}, {"description": "Create an API Rule to expose the Python Serverless Function externally.", "assigned_to": "KymaAgent", "status": "pending", "result": null}]}}',
            b'{"event": "agent_action", "data": {"agent": "Supervisor", "answer": {"messages": [{"content": "{\\n  \\"next\\": \\"KymaAgent\\"\\n}", "additional_kwargs": {}, "response_metadata": {}, "type": "ai", "name": "Supervisor", "id": null, "example": false, "tool_calls": [], "invalid_tool_calls": [], "usage_metadata": null}], "next": "KymaAgent", "subtasks": [{"description": "Create a Hello World Python Serverless Function in Kyma.", "assigned_to": "KymaAgent", "status": "pending", "result": null}, {"description": "Create an API Rule to expose the Python Serverless Function externally.", "assigned_to": "KymaAgent", "status": "pending", "result": null}]}}}',
        ),
        (
            b'{"KymaAgent": {"messages": [{"content": "To create an API Rule in Kyma to expose a service externally"}]}}',
            b'{"event": "agent_action", "data": {"agent": "KymaAgent", "answer": {"messages": [{"content": "To create an API Rule in Kyma to expose a service externally"}]}}}',
        ),
        (
            b'{"KubernetesAgent": {"messages": [{"content": "To create a kubernetes deployment"}]}}',
            b'{"event": "agent_action", "data": {"agent": "KubernetesAgent", "answer": {"messages": [{"content": "To create a kubernetes deployment"}]}}}',
        ),
        (
            b'{"Exit": {"next": "__end__", "final_response": "To create a Kubernetes application and expose it when deployed in the Kyma runtime"}}',
            b'{"event": "final_response", "data": {"answer": "To create a Kubernetes application and expose it when deployed in the Kyma runtime"}}',
        ),
    ],
)
def test_prepare_chunk_response(chunk, expected):
    assert prepare_chunk_response(chunk) == expected
