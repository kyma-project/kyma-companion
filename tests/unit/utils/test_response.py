from unittest.mock import Mock, patch

import pytest

from utils.response import prepare_chunk_response


@pytest.mark.parametrize(
    "input, expected",
    [
        (
            # input Direct response from planner
            b'{"KubernetesAgent": { "messages": [{"additional_kwargs": {}, "content": "The Pod named is running and ready.", '
            b'"name": "KubernetesAgent"}], '
            b'"subtasks": '
            b'[{"assigned_to": "KubernetesAgent", "description": "what is my pods status", "status": "completed", "task_title": "Checking status of pods"}, '
            b'{"assigned_to": "Common", "description": "how to write hello world code in python", "status": "pending", "task_title": "Retrieving hello world code in python"}, '
            b'{"assigned_to": "KymaAgent", "description": "how to create kyma function", "status": "pending", "task_title": "Fetching steps to create kyma function"}], "next": "__end__"}}',
            # expected
            b'{"event": "agent_action", "data": {"agent": "KubernetesAgent", "answer": {"c'
            b'ontent": "The Pod named is running and ready.", "tasks": [{"task_id": 0, "ta'
            b'sk_name": "Checking status of pods", "status": "completed", "agent": "Kubern'
            b'etesAgent"}, {"task_id": 1, "task_name": "Retrieving hello world code in pyt'
            b'hon", "status": "pending", "agent": "Common"}, {"task_id": 2, "task_name": "'
            b'Fetching steps to create kyma function", "status": "pending", "agent": "Kyma'
            b'Agent"}], "next": "Common"}}}',
        ),
        (
            # input
            b'{"Supervisor": {"messages": [{"additional_kwargs": {}, "content": "The capital of India is New Delhi.", '
            b'"name": "Planner", "response_metadata": {}, "tool_calls": []}], '
            b'"subtasks": [], "next": "__end__", "error": null}}',
            # expected
            b'{"event": "agent_action", "data": {"agent": "Supervisor", "answer": {"conten'
            b't": "The capital of India is New Delhi.", "tasks": [], "next": "__end__"}}}',
        ),
        (b'{"Summarization": {"messages": []}}', None),
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
