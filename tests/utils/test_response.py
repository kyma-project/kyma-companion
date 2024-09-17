# write test that tests the prepare_response_chunk function
import pytest

from utils.response import prepare_chunk_response


@pytest.mark.parametrize(
    "chunk, expected",
    [
        (
            b'{"Planner": {"messages": [{"content": "Task decomposed into subtasks and assigned to agents: [{"description": "Create a Kubernetes Deployment for the application.", "assigned_to": "KubernetesAgent", "status": "pending", "result": null}, {"description": "Create a Kubernetes Service to expose the application within the cluster.", "assigned_to": "KubernetesAgent", "status": "pending", "result": null}, {"description": "Create an API Rule in Kyma to expose the application externally.", "assigned_to": "KymaAgent", "status": "pending", "result": null}]", "additional_kwargs": {}, "response_metadata": {}, "type": "ai", "name": "Planner", "id": null, "example": false, "tool_calls": [], "invalid_tool_calls": [], "usage_metadata": null}], "next": "Continue", "subtasks": [{"description": "Create a Kubernetes Deployment for the application.", "assigned_to": "KubernetesAgent", "status": "pending", "result": null}, {"description": "Create a Kubernetes Service to expose the application within the cluster.", "assigned_to": "KubernetesAgent", "status": "pending", "result": null}, {"description": "Create an API Rule in Kyma to expose the application externally.", "assigned_to": "KymaAgent", "status": "pending", "result": null}], "final_response": null, "error": null}}',
            '{"event": "agent_action", "data": {"agent": "Planner", "answer": {"messages": [{"content": "Task decomposed into subtasks and assigned to agents: [{"description": "Create a Kubernetes Deployment for the application.", "assigned_to": "KubernetesAgent", "status": "pending", "result": null}, {"description": "Create a Kubernetes Service to expose the application within the cluster.", "assigned_to": "KubernetesAgent", "status": "pending", "result": null}, {"description": "Create an API Rule in Kyma to expose the application externally.", "assigned_to": "KymaAgent", "status": "pending", "result": null}]", "additional_kwargs": {}, "response_metadata": {}, "type": "ai", "name": "Planner", "id": null, "example": false, "tool_calls": [], "invalid_tool_calls": [], "usage_metadata": null}], "next": "Continue", "subtasks": [{"description": "Create a Kubernetes Deployment for the application.", "assigned_to": "KubernetesAgent", "status": "pending", "result": null}, {"description": "Create a Kubernetes Service to expose the application within the cluster.", "assigned_to": "KubernetesAgent", "status": "pending", "result": null}, {"description": "Create an API Rule in Kyma to expose the application externally.", "assigned_to": "KymaAgent", "status": "pending", "result": null}], "final_response": null, "error": null}}',
        ),
        (
            b'{"KymaAgent": {"messages": [{"content": "To create an API Rule in Kyma to expose a service externally"}]}}',
            '{"event": "agent_action", "data": {"agent": "KymaAgent", "answer": {"messages": [{"content": "To create an API Rule in Kyma to expose a service externally"}]}}}',
        ),
        (
            b'{"KubernetesAgent": {"messages": [{"content": "To create a kubernetes deployment"}]}}',
            '{"event": "agent_action", "data": {"agent": "KubernetesAgent", "answer": {"messages": [{"content": "To create a kubernetes deployment"}]}}}',
        ),
        (
            b'{"Exit": {"next": "__end__", "final_response": "To create a Kubernetes application and expose it when deployed in the Kyma runtime"}}',
            '{"event": "final_response", "data": {"answer": "To create a Kubernetes application and expose it when deployed in the Kyma runtime"}}',
        ),
    ],
)
def test_prepare_chunk_response(chunk, expected):
    assert prepare_chunk_response(chunk) == expected
