"""Tests for SSE event formatter: format, structure, and contract matching."""

import json

import pytest

from utils.streaming import (
    build_tasks_list,
    format_sse_event,
    make_error_event,
    make_final_event,
    make_planning_event,
    make_tool_event,
)


class TestFormatSseEvent:
    """Tests for format_sse_event base function."""

    def test_returns_bytes(self):
        result = format_sse_event("test_event", {"key": "value"})
        assert isinstance(result, bytes)

    def test_valid_json(self):
        result = format_sse_event("test_event", {"key": "value"})
        parsed = json.loads(result)
        assert parsed["event"] == "test_event"
        assert parsed["data"]["key"] == "value"

    def test_event_structure(self):
        result = format_sse_event("my_event", {"foo": "bar"})
        parsed = json.loads(result)
        assert "event" in parsed
        assert "data" in parsed
        assert parsed["event"] == "my_event"

    def test_empty_data(self):
        result = format_sse_event("evt", {})
        parsed = json.loads(result)
        assert parsed["data"] == {}

    def test_nested_data(self):
        data = {"answer": {"content": "hello", "tasks": []}}
        result = format_sse_event("evt", data)
        parsed = json.loads(result)
        assert parsed["data"]["answer"]["content"] == "hello"


class TestMakePlanningEvent:
    """Tests for make_planning_event."""

    def test_returns_bytes(self):
        assert isinstance(make_planning_event(), bytes)

    def test_event_type(self):
        parsed = json.loads(make_planning_event())
        assert parsed["event"] == "agent_action"

    def test_agent_is_gatekeeper(self):
        parsed = json.loads(make_planning_event())
        assert parsed["data"]["agent"] == "Gatekeeper"

    def test_error_is_none(self):
        parsed = json.loads(make_planning_event())
        assert parsed["data"]["error"] is None

    def test_tasks_contains_planning(self):
        parsed = json.loads(make_planning_event())
        tasks = parsed["data"]["answer"]["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["task_name"] == "Planning your request..."
        assert tasks[0]["status"] == "pending"
        assert tasks[0]["agent"] == "Planner"
        assert tasks[0]["task_id"] == 0

    def test_next_is_supervisor(self):
        parsed = json.loads(make_planning_event())
        assert parsed["data"]["answer"]["next"] == "Supervisor"

    def test_content_is_empty(self):
        parsed = json.loads(make_planning_event())
        assert parsed["data"]["answer"]["content"] == ""


class TestMakeToolEvent:
    """Tests for make_tool_event."""

    def test_returns_bytes(self):
        assert isinstance(make_tool_event("tool_a", 1), bytes)

    def test_event_type(self):
        parsed = json.loads(make_tool_event("tool_a", 1))
        assert parsed["event"] == "agent_action"

    def test_agent_is_tool_name(self):
        parsed = json.loads(make_tool_event("k8s_query_tool", 1))
        assert parsed["data"]["agent"] == "k8s_query_tool"

    def test_error_is_none(self):
        parsed = json.loads(make_tool_event("tool_a", 1))
        assert parsed["data"]["error"] is None

    def test_custom_tasks(self):
        tasks = [{"task_id": 0, "task_name": "Done", "status": "completed", "agent": "Planner"}]
        parsed = json.loads(make_tool_event("tool_a", 1, tasks=tasks))
        assert parsed["data"]["answer"]["tasks"] == tasks

    def test_default_empty_tasks(self):
        parsed = json.loads(make_tool_event("tool_a", 1))
        assert parsed["data"]["answer"]["tasks"] == []

    def test_next_is_none(self):
        parsed = json.loads(make_tool_event("tool_a", 1))
        assert parsed["data"]["answer"]["next"] is None


class TestMakeFinalEvent:
    """Tests for make_final_event."""

    def test_returns_bytes(self):
        assert isinstance(make_final_event("Answer"), bytes)

    def test_agent_is_finalizer(self):
        parsed = json.loads(make_final_event("Answer"))
        assert parsed["data"]["agent"] == "Finalizer"

    def test_content_matches(self):
        parsed = json.loads(make_final_event("My answer"))
        assert parsed["data"]["answer"]["content"] == "My answer"

    def test_next_is_end(self):
        parsed = json.loads(make_final_event("Answer"))
        assert parsed["data"]["answer"]["next"] == "__end__"

    def test_error_default_none(self):
        parsed = json.loads(make_final_event("Answer"))
        assert parsed["data"]["error"] is None

    def test_error_custom(self):
        parsed = json.loads(make_final_event("Answer", error="something went wrong"))
        assert parsed["data"]["error"] == "something went wrong"

    def test_tasks_default_empty(self):
        parsed = json.loads(make_final_event("Answer"))
        assert parsed["data"]["answer"]["tasks"] == []

    def test_tasks_custom(self):
        tasks = [{"task_id": 0, "task_name": "Plan", "status": "completed", "agent": "Planner"}]
        parsed = json.loads(make_final_event("Answer", tasks=tasks))
        assert parsed["data"]["answer"]["tasks"] == tasks

    def test_empty_content(self):
        parsed = json.loads(make_final_event(""))
        assert parsed["data"]["answer"]["content"] == ""


class TestMakeErrorEvent:
    """Tests for make_error_event."""

    def test_returns_bytes(self):
        assert isinstance(make_error_event("error msg"), bytes)

    def test_event_type_is_unknown(self):
        parsed = json.loads(make_error_event("error msg"))
        assert parsed["event"] == "unknown"

    def test_agent_is_none(self):
        parsed = json.loads(make_error_event("error msg"))
        assert parsed["data"]["agent"] is None

    def test_error_message_in_data(self):
        parsed = json.loads(make_error_event("Something failed"))
        assert parsed["data"]["error"] == "Something failed"

    def test_content_matches_error(self):
        parsed = json.loads(make_error_event("Something failed"))
        assert parsed["data"]["answer"]["content"] == "Something failed"

    def test_next_is_end(self):
        parsed = json.loads(make_error_event("error"))
        assert parsed["data"]["answer"]["next"] == "__end__"

    def test_tasks_empty(self):
        parsed = json.loads(make_error_event("error"))
        assert parsed["data"]["answer"]["tasks"] == []


class TestBuildTasksList:
    """Tests for build_tasks_list function."""

    def test_empty_tool_calls(self):
        tasks = build_tasks_list([])
        assert len(tasks) == 1
        assert tasks[0]["task_id"] == 0
        assert tasks[0]["task_name"] == "Planning your request..."
        assert tasks[0]["status"] == "completed"
        assert tasks[0]["agent"] == "Planner"

    def test_completed_tool_calls(self):
        tool_calls = [
            {"name": "k8s_query_tool", "task_title": "Queried k8s_query_tool", "agent": "k8s_query_tool"},
        ]
        tasks = build_tasks_list(tool_calls)
        assert len(tasks) == 2
        # Planning task
        assert tasks[0]["status"] == "completed"
        # Tool call task
        assert tasks[1]["task_id"] == 1
        assert tasks[1]["task_name"] == "Queried k8s_query_tool"
        assert tasks[1]["status"] == "completed"

    def test_current_tool_in_progress(self):
        tool_calls = [
            {"name": "k8s_query_tool", "task_title": "Queried k8s_query_tool", "agent": "k8s_query_tool"},
        ]
        tasks = build_tasks_list(tool_calls, current_tool="kyma_query_tool")
        assert len(tasks) == 3
        # Last task is in progress
        last_task = tasks[-1]
        assert last_task["status"] == "in_progress"
        assert last_task["task_name"] == "Calling kyma_query_tool..."
        assert last_task["agent"] == "kyma_query_tool"
        assert last_task["task_id"] == 2

    def test_no_current_tool(self):
        tasks = build_tasks_list([], current_tool=None)
        # Only planning task
        assert len(tasks) == 1

    @pytest.mark.parametrize(
        "tool_calls_count",
        [1, 3, 5],
    )
    def test_task_ids_sequential(self, tool_calls_count):
        tool_calls = [
            {"name": f"tool_{i}", "task_title": f"Task {i}", "agent": f"tool_{i}"}
            for i in range(tool_calls_count)
        ]
        tasks = build_tasks_list(tool_calls)
        for i, task in enumerate(tasks):
            assert task["task_id"] == i

    def test_task_title_fallback_to_name(self):
        """When task_title is missing, fall back to name."""
        tool_calls = [{"name": "my_tool", "agent": "my_tool"}]
        tasks = build_tasks_list(tool_calls)
        assert tasks[1]["task_name"] == "my_tool"


class TestSSEEventContract:
    """Cross-cutting tests verifying SSE events match the expected contract."""

    @pytest.mark.parametrize(
        "event_bytes",
        [
            make_planning_event(),
            make_tool_event("test_tool", 1),
            make_final_event("content"),
            make_error_event("error"),
        ],
    )
    def test_all_events_are_valid_json_bytes(self, event_bytes):
        assert isinstance(event_bytes, bytes)
        parsed = json.loads(event_bytes)
        assert "event" in parsed
        assert "data" in parsed

    @pytest.mark.parametrize(
        "event_bytes",
        [
            make_planning_event(),
            make_tool_event("test_tool", 1),
            make_final_event("content"),
            make_error_event("error"),
        ],
    )
    def test_all_events_have_answer_structure(self, event_bytes):
        parsed = json.loads(event_bytes)
        answer = parsed["data"]["answer"]
        assert "content" in answer
        assert "tasks" in answer
        assert isinstance(answer["tasks"], list)

    @pytest.mark.parametrize(
        "event_bytes",
        [
            make_planning_event(),
            make_tool_event("test_tool", 1),
            make_final_event("content"),
            make_error_event("error"),
        ],
    )
    def test_all_events_have_agent_field(self, event_bytes):
        parsed = json.loads(event_bytes)
        assert "agent" in parsed["data"]

    @pytest.mark.parametrize(
        "event_bytes",
        [
            make_planning_event(),
            make_tool_event("test_tool", 1),
            make_final_event("content"),
            make_error_event("error"),
        ],
    )
    def test_all_events_have_error_field(self, event_bytes):
        parsed = json.loads(event_bytes)
        assert "error" in parsed["data"]
