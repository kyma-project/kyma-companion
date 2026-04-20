"""SSE event formatter matching existing prepare_chunk_response output format."""

from __future__ import annotations

import json
from typing import Any


def format_sse_event(
    event: str,
    data: dict[str, Any],
) -> bytes:
    """Format a single SSE event as bytes.

    Args:
        event: Event type (e.g., "agent_action").
        data: Event payload.

    Returns:
        JSON-encoded bytes ready for streaming.
    """
    return json.dumps({"event": event, "data": data}).encode()


def make_planning_event() -> bytes:
    """Create the initial 'planning your request' SSE event."""
    return format_sse_event(
        "agent_action",
        {
            "agent": "Gatekeeper",
            "error": None,
            "answer": {
                "content": "",
                "tasks": [
                    {
                        "task_id": 0,
                        "task_name": "Planning your request...",
                        "status": "pending",
                        "agent": "Planner",
                    }
                ],
                "is_feedback": None,
                "next": "Supervisor",
            },
        },
    )


def make_tool_event(
    tool_name: str,
    tool_task_id: int,
    status: str = "in_progress",
    tasks: list[dict] | None = None,
) -> bytes:
    """Create an SSE event for tool execution progress."""
    if tasks is None:
        tasks = []
    return format_sse_event(
        "agent_action",
        {
            "agent": tool_name,
            "error": None,
            "answer": {
                "content": "",
                "tasks": tasks,
                "next": None,
            },
        },
    )


def make_final_event(
    content: str,
    tasks: list[dict] | None = None,
    error: str | None = None,
) -> bytes:
    """Create the final answer SSE event."""
    if tasks is None:
        tasks = []
    return format_sse_event(
        "agent_action",
        {
            "agent": "Finalizer",
            "error": error,
            "answer": {
                "content": content,
                "tasks": tasks,
                "next": "__end__",
            },
        },
    )


def make_gatekeeper_event(content: str) -> bytes:
    """Create an SSE event for a direct gatekeeper response (no agent needed)."""
    return format_sse_event(
        "agent_action",
        {
            "agent": "Gatekeeper",
            "error": None,
            "answer": {
                "content": content,
                "tasks": [],
                "next": "__end__",
            },
        },
    )


def make_error_event(error_message: str) -> bytes:
    """Create an error SSE event."""
    return format_sse_event(
        "unknown",
        {
            "agent": None,
            "error": error_message,
            "answer": {
                "content": error_message,
                "tasks": [],
                "next": "__end__",
            },
        },
    )


def build_tasks_list(
    tool_calls_made: list[dict],
    current_tool: str | None = None,
) -> list[dict]:
    """Build the tasks list for SSE events.

    Shows planning as completed, past tools as completed,
    current tool as in_progress.

    Args:
        tool_calls_made: List of completed tool calls with name/task_title.
        current_tool: Name of the currently executing tool (None if done).

    Returns:
        Tasks list matching the existing SSE format.
    """
    tasks = [
        {
            "task_id": 0,
            "task_name": "Planning your request...",
            "status": "completed",
            "agent": "Planner",
        }
    ]

    for i, tc in enumerate(tool_calls_made, 1):
        task_name = tc.get("task_title", tc.get("name", f"Tool call {i}"))
        tasks.append(
            {
                "task_id": i,
                "task_name": task_name,
                "status": "completed",
                "agent": tc.get("agent", tc.get("name", "")),
            }
        )

    if current_tool:
        tasks.append(
            {
                "task_id": len(tool_calls_made) + 1,
                "task_name": f"Calling {current_tool}...",
                "status": "in_progress",
                "agent": current_tool,
            }
        )

    return tasks
