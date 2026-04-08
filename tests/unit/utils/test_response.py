import json
from unittest.mock import Mock, patch

import pytest

from agents.common.constants import (
    FINALIZER,
    GATEKEEPER,
    NEXT,
    PLANNER,
)
from agents.common.state import SubTaskStatus
from agents.supervisor.agent import SUPERVISOR
from utils.response import prepare_chunk_response, process_response, reformat_subtasks


def test_process_response_gatekeeper_forwarded_to_supervisor():
    """Test gatekeeper forwarding to supervisor"""
    data = {GATEKEEPER: {NEXT: SUPERVISOR, "messages": []}}

    result = process_response(data, GATEKEEPER)

    assert result is not None
    assert result["agent"] == GATEKEEPER
    assert result["error"] is None
    assert result["answer"]["content"] == ""
    assert result["answer"][NEXT] == SUPERVISOR
    assert len(result["answer"]["tasks"]) == 1
    assert result["answer"]["tasks"][0]["task_name"] == "Planning your request..."
    assert result["answer"]["tasks"][0]["status"] == SubTaskStatus.PENDING


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
            b'{"assigned_to": "KymaAgent", "description": "how to write hello world code in python", "status": "pending", "task_title": "Retrieving hello world code in python"}, '
            b'{"assigned_to": "KymaAgent", "description": "how to create kyma function", "status": "pending", "task_title": "Fetching steps to create kyma function"}], "next": "__end__"}}',
            # expected
            b'{"event": "agent_action", "data": {"agent": "KubernetesAgent", "answer": {"c'
            b'ontent": "The Pod named is running and ready.", "tasks": [{"task_id": 0, "ta'
            b'sk_name": "Planning your request...", "status": "completed", "agent": "Plann'
            b'er"}, {"task_id": 1, "task_name": "Checking status of pods", "status": "comp'
            b'leted", "agent": "KubernetesAgent"}, {"task_id": 2, "task_name": "Retrieving'
            b' hello world code in python", "status": "pending", "agent": "KymaAgent"}, {"tas'
            b'k_id": 3, "task_name": "Fetching steps to create kyma function", "status": "'
            b'pending", "agent": "KymaAgent"}], "next": "KymaAgent"}, "error": null}}',
        ),
        (
            # Supervisor Agent with last agent planner
            # input
            b'{"Supervisor": { "messages": [{"additional_kwargs": {}, "content": "", '
            b'"name": "Planner"}], '
            b'"subtasks": '
            b'[{"assigned_to": "KubernetesAgent", "description": "what is my pods status", "status": "pending", "task_title": "Checking status of pods"}, '
            b'{"assigned_to": "KymaAgent", "description": "how to write hello world code in python", "status": "pending", "task_title": "Retrieving hello world code in python"}, '
            b'{"assigned_to": "KymaAgent", "description": "how to create kyma function", "status": "pending", "task_title": "Fetching steps to create kyma function"}], "next": "KubernetesAgent"}}',
            # expected
            b'{"event": "agent_action", "data": {"agent": "Supervisor", "answer": {"conten'
            b't": "", "tasks": [{"task_id": 0, "task_name": "Planning your request...", "s'
            b'tatus": "completed", "agent": "Planner"}, {"task_id": 1, "task_name": "Check'
            b'ing status of pods", "status": "pending", "agent": "KubernetesAgent"}, {"tas'
            b'k_id": 2, "task_name": "Retrieving hello world code in python", "status": "p'
            b'ending", "agent": "KymaAgent"}, {"task_id": 3, "task_name": "Fetching steps to '
            b'create kyma function", "status": "pending", "agent": "KymaAgent"}], "next": '
            b'"KubernetesAgent"}, "error": null}}',
        ),
        (
            # Supervisor Agent with last agent finalizer
            # input
            b'{"Supervisor": { "messages": [{"additional_kwargs": {}, "content": "final response", '
            b'"name": "Finalizer"}], '
            b'"subtasks": '
            b'[{"assigned_to": "KubernetesAgent", "description": "what is my pods status", "status": "completed", "task_title": "Checking status of pods"}, '
            b'{"assigned_to": "KymaAgent", "description": "how to write hello world code in python", "status": "completed", "task_title": "Retrieving hello world code in python"}, '
            b'{"assigned_to": "KymaAgent", "description": "how to create kyma function", "status": "completed", "task_title": "Fetching steps to create kyma function"}], "next": "__end__"}}',
            # expected
            b'{"event": "agent_action", "data": {"agent": "Supervisor", "answer": {"conten'
            b't": "final response", "tasks": [{"task_id": 0, "task_name": "Planning your r'
            b'equest...", "status": "completed", "agent": "Planner"}, {"task_id": 1, "task'
            b'_name": "Checking status of pods", "status": "completed", "agent": "Kubernet'
            b'esAgent"}, {"task_id": 2, "task_name": "Retrieving hello world code in pytho'
            b'n", "status": "completed", "agent": "KymaAgent"}, {"task_id": 3, "task_name": "'
            b'Fetching steps to create kyma function", "status": "completed", "agent": "Ky'
            b'maAgent"}], "next": "__end__"}, "error": null}}',
        ),
        (
            # Skip response from supervisor if agent is not planner or not finalizer
            # input
            b'{"Supervisor": { "messages": [{"additional_kwargs": {}, "content": "The Pod named is running and ready.", '
            b'"name": "KubernetesAgent"}], '
            b'"subtasks": '
            b'[{"assigned_to": "KubernetesAgent", "description": "what is my pods status", "status": "completed", "task_title": "Checking status of pods"}, '
            b'{"assigned_to": "KymaAgent", "description": "how to write hello world code in python", "status": "pending", "task_title": "Retrieving hello world code in python"}, '
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
        (
            # input
            b'{"KubernetesAgent": {"error": "Error occurred"}}',
            # expected
            b'{"event": "agent_action", "data": {"agent": "KubernetesAgent", "answer": {"t'
            b'asks": []}, "error": "Error occurred"}}',
        ),
        (
            # KymaAgent with error and empty subtasks
            # input
            b'{"KymaAgent": {"error": "Kyma service unavailable", "messages": [], "subtasks": []}}',
            # expected
            b'{"event": "agent_action", "data": {"agent": "KymaAgent", "answer": {"tasks"'
            b': []}, "error": "Kyma service unavailable"}}',
        ),
        (
            # Regular agent with error and some content
            # input
            b'{"KymaAgent": {"error": "Network timeout", "messages": [{"content": "Partial response", "name": "KymaAgent"}], "subtasks": []}}',
            # expected
            b'{"event": "agent_action", "data": {"agent": "KymaAgent", "answer": {"content":'
            b' "Partial response", "tasks": []}, "error": "Network timeout"}}',
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
        (
            b'{"error": {"error":"We encountered an error while processing your request. Please try again shortly. Thank you for your patience!"}}',
            b'{"event": "unknown", "data": {"agent": null, "error": "We encountered an err'
            b"or while processing your request. Please try again shortly. Thank you for yo"
            b'ur patience!", "answer": {"content": "We encountered an error while processi'
            b'ng your request. Please try again shortly. Thank you for your patience!", "t'
            b'asks": [], "next": "__end__"}}}',
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
                    "agent": "Planner",
                    "status": "completed",
                    "task_id": 0,
                    "task_name": "Planning your request...",
                },
                {
                    "task_id": 1,
                    "task_name": "Checking status of pods",
                    "status": "completed",
                    "agent": "KubernetesAgent",
                },
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
                    "assigned_to": "KymaAgent",
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
                    "agent": "Planner",
                    "status": "completed",
                    "task_id": 0,
                    "task_name": "Planning your request...",
                },
                {
                    "task_id": 1,
                    "task_name": "Checking status of pods",
                    "status": "completed",
                    "agent": "KubernetesAgent",
                },
                {
                    "task_id": 2,
                    "task_name": "Retrieving hello world code in python",
                    "status": "pending",
                    "agent": "KymaAgent",
                },
                {
                    "task_id": 3,
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


@pytest.mark.parametrize(
    "agent,messages,last_agent,has_error,expected_skip,description",
    [
        # Skipping scenarios
        (
            SUPERVISOR,
            [{"name": "intermediate_agent", "content": "test"}],
            "intermediate_agent",
            False,
            True,
            "supervisor_with_intermediate_agent",
        ),
        (
            SUPERVISOR,
            [{"name": "random_agent", "content": "test"}],
            "random_agent",
            False,
            True,
            "supervisor_with_random_agent",
        ),
        (
            SUPERVISOR,
            [{"name": "some_other", "content": "test"}],
            "some_other",
            False,
            True,
            "supervisor_with_other_agent",
        ),
        # Non-skipping scenarios
        (
            SUPERVISOR,
            [{"name": PLANNER, "content": "test"}],
            PLANNER,
            False,
            False,
            "supervisor_with_planner",
        ),
        (
            SUPERVISOR,
            [{"name": FINALIZER, "content": "test"}],
            FINALIZER,
            False,
            False,
            "supervisor_with_finalizer",
        ),
        (SUPERVISOR, [], None, False, False, "supervisor_without_messages"),
        (
            PLANNER,
            [{"name": "any_agent", "content": "test"}],
            "any_agent",
            False,
            False,
            "planner_agent",
        ),
        (
            GATEKEEPER,
            [{"name": "any_agent", "content": "test"}],
            "any_agent",
            False,
            False,
            "gatekeeper_agent",
        ),
        (
            FINALIZER,
            [{"name": "any_agent", "content": "test"}],
            "any_agent",
            False,
            False,
            "finalizer_agent",
        ),
        (
            "custom_agent",
            [{"name": "any_agent", "content": "test"}],
            "any_agent",
            False,
            False,
            "custom_agent",
        ),
    ],
)
def test_prepare_chunk_response_all_skipping_scenarios(
    agent, messages, last_agent, has_error, expected_skip, description
):
    """
    Comprehensive test for all agent skipping and non-skipping scenarios in prepare_chunk_response.

    Tests the following skipping logic:
    1. Supervisor responses are skipped when last_agent is not PLANNER or FINALIZER
    2. All other agents are processed normally
    """
    # Prepare chunk data
    chunk_data = {agent: {}}
    if messages is not None:
        chunk_data[agent]["messages"] = messages

    # Add error if specified
    if has_error:
        chunk_data[agent]["error"] = f"{agent} error occurred"

    chunk = json.dumps(chunk_data).encode()

    mock_process_return = {
        "agent": agent,
        "answer": {"content": "test response", "tasks": []},
        "error": None,
    }

    with patch("utils.response.process_response") as mock_process:
        mock_process.return_value = mock_process_return

        result = prepare_chunk_response(chunk)

        if expected_skip:
            # Should return None (skipped)
            assert result is None, f"Expected {description} to be skipped, but got result: {result}"

        else:
            # Should return a valid response
            assert result is not None, f"Expected {description} to return result, but got None"

            # Decode and verify response structure
            result_dict = json.loads(result.decode())
            assert result_dict["data"] == mock_process_return

            # process_response should be called
            mock_process.assert_called_once_with(chunk_data, agent)
