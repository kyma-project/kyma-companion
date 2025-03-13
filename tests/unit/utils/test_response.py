from unittest.mock import Mock, patch

import pytest

from utils.response import prepare_chunk_response, reformat_subtasks


@pytest.mark.parametrize(
    "input, expected",
    [
        (
            # Agent Response with tasks
            # input
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
            b'Agent"}], "next": "Common"}, "error": null}}',
        ),
        (
            # Supervisor Agent with last agent planner
            # input
            b'{"Supervisor": { "messages": [{"additional_kwargs": {}, "content": "", '
            b'"name": "Planner"}], '
            b'"subtasks": '
            b'[{"assigned_to": "KubernetesAgent", "description": "what is my pods status", "status": "pending", "task_title": "Checking status of pods"}, '
            b'{"assigned_to": "Common", "description": "how to write hello world code in python", "status": "pending", "task_title": "Retrieving hello world code in python"}, '
            b'{"assigned_to": "KymaAgent", "description": "how to create kyma function", "status": "pending", "task_title": "Fetching steps to create kyma function"}], "next": "KubernetesAgent"}}',
            # expected
            b'{"event": "agent_action", "data": {"agent": "Supervisor", "answer": {"c'
            b'ontent": "", "tasks": [{"task_id": 0, "ta'
            b'sk_name": "Checking status of pods", "status": "pending", "agent": "Kubern'
            b'etesAgent"}, {"task_id": 1, "task_name": "Retrieving hello world code in pyt'
            b'hon", "status": "pending", "agent": "Common"}, {"task_id": 2, "task_name": "'
            b'Fetching steps to create kyma function", "status": "pending", "agent": "Kyma'
            b'Agent"}], "next": "KubernetesAgent"}, "error": null}}',
        ),
        (
            # Supervisor Agent with last agent finalizer
            # input
            b'{"Supervisor": { "messages": [{"additional_kwargs": {}, "content": "final response", '
            b'"name": "Finalizer"}], '
            b'"subtasks": '
            b'[{"assigned_to": "KubernetesAgent", "description": "what is my pods status", "status": "completed", "task_title": "Checking status of pods"}, '
            b'{"assigned_to": "Common", "description": "how to write hello world code in python", "status": "completed", "task_title": "Retrieving hello world code in python"}, '
            b'{"assigned_to": "KymaAgent", "description": "how to create kyma function", "status": "completed", "task_title": "Fetching steps to create kyma function"}], "next": "__end__"}}',
            # expected
            b'{"event": "agent_action", "data": {"agent": "Supervisor", "answer": {"c'
            b'ontent": "final response", "tasks": [{"task_id": 0, "ta'
            b'sk_name": "Checking status of pods", "status": "completed", "agent": "Kubern'
            b'etesAgent"}, {"task_id": 1, "task_name": "Retrieving hello world code in pyt'
            b'hon", "status": "completed", "agent": "Common"}, {"task_id": 2, "task_name": "'
            b'Fetching steps to create kyma function", "status": "completed", "agent": "Kyma'
            b'Agent"}], "next": "__end__"}, "error": null}}',
        ),
        (
            # Skip response from supervisor if agent is not planner or not finalizer
            # input
            b'{"Supervisor": { "messages": [{"additional_kwargs": {}, "content": "The Pod named is running and ready.", '
            b'"name": "KubernetesAgent"}], '
            b'"subtasks": '
            b'[{"assigned_to": "KubernetesAgent", "description": "what is my pods status", "status": "completed", "task_title": "Checking status of pods"}, '
            b'{"assigned_to": "Common", "description": "how to write hello world code in python", "status": "pending", "task_title": "Retrieving hello world code in python"}, '
            b'{"assigned_to": "KymaAgent", "description": "how to create kyma function", "status": "pending", "task_title": "Fetching steps to create kyma function"}], "next": "KymaAgent"}}',
            # expected
            None,
        ),
        (
            # Direct response from planner
            # input
            b'{"Supervisor": {"messages": [{"additional_kwargs": {}, "content": "The capital of India is New Delhi.", '
            b'"name": "Planner", "response_metadata": {}, "tool_calls": []}], '
            b'"subtasks": [], "next": "__end__", "error": null}}',
            # expected
            b'{"event": "agent_action", "data": {"agent": "Supervisor", "answer": {"conten'
            b't": "The capital of India is New Delhi.", "tasks": [], "next": "__end__"}, "'
            b'error": null}}',
        ),
        # Skip response if agent is Summarization
        (b'{"Summarization": {"messages": []}}', None),
        (
            # input
            b'{"KubernetesAgent": {"error": "Error occurred"}}',
            # expected
            b'{"event": "agent_action", "data": {"agent": "KubernetesAgent", "answer": {"t'
            b'asks": []}, "error": "Error occurred"}}',
        ),
        (
            # Error response for invalid json
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


@pytest.mark.parametrize(
    "subtasks, expected_output",
    [
        # Test case 1: Empty subtasks
        ([], []),
        # Test case 2: Single subtask
        (
            [
                {
                    "assigned_to": "KubernetesAgent",
                    "description": "what is my pods status",
                    "status": "completed",
                    "task_title": "Checking status of pods",
                }
            ],
            [
                {
                    "task_id": 0,
                    "task_name": "Checking status of pods",
                    "status": "completed",
                    "agent": "KubernetesAgent",
                }
            ],
        ),
        # Test case 3: Multiple subtasks
        (
            [
                {
                    "assigned_to": "KubernetesAgent",
                    "description": "what is my pods status",
                    "status": "completed",
                    "task_title": "Checking status of pods",
                },
                {
                    "assigned_to": "Common",
                    "description": "how to write hello world code in python",
                    "status": "pending",
                    "task_title": "Retrieving hello world code in python",
                },
                {
                    "assigned_to": "KymaAgent",
                    "description": "how to create kyma function",
                    "status": "pending",
                    "task_title": "Fetching steps to create kyma function",
                },
            ],
            [
                {
                    "task_id": 0,
                    "task_name": "Checking status of pods",
                    "status": "completed",
                    "agent": "KubernetesAgent",
                },
                {
                    "task_id": 1,
                    "task_name": "Retrieving hello world code in python",
                    "status": "pending",
                    "agent": "Common",
                },
                {
                    "task_id": 2,
                    "task_name": "Fetching steps to create kyma function",
                    "status": "pending",
                    "agent": "KymaAgent",
                },
            ],
        ),
        # Test case 4: Missing keys (should raise KeyError)
        (
            [
                {
                    "assigned_to": "KubernetesAgent",
                    "description": "what is my pods status",
                    "status": "completed",
                }
            ],
            KeyError,
        ),
        # Test case 5: Incorrect data types (should raise TypeError)
        ("not a dictionary", TypeError),
        # Test case 6: None input
        (None, []),
    ],
)
def test_reformat_subtasks(subtasks, expected_output):
    if expected_output in [KeyError, TypeError]:
        with pytest.raises(expected_output):
            reformat_subtasks(subtasks)
    else:
        result = reformat_subtasks(subtasks)
        assert result == expected_output
