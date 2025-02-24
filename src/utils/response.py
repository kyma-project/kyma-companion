import json
from typing import Any

from agents.common.constants import (
    FINALIZER,
    NEXT,
    PLANNER,
    SUMMARIZATION,
)
from agents.common.state import SubTaskStatus
from agents.supervisor.agent import SUPERVISOR
from utils.logging import get_logger

logger = get_logger(__name__)


def reformat_subtasks(subtasks: list[dict[Any, Any]]) -> list[dict[str, Any]]:
    """Reformat subtasks list for companion response"""
    tasks = []
    if subtasks:
        for i, subtask in enumerate(subtasks):
            task = {
                "task_id": i,
                "task_name": subtask["task_title"],
                "status": subtask["status"],
                "agent": subtask["assigned_to"],
            }

            tasks.append(task)
    return tasks


def process_response(data: dict[str, Any], agent: str) -> dict[str, Any] | None:
    """Process agent data and return the last message only."""
    agent_data = data[agent]
    agent_error = None
    if "error" in agent_data and agent_data["error"]:
        agent_error = agent_data["error"]
        if agent == SUMMARIZATION:
            # we don't show summarization node, but only error
            return {"agent": None,  "error": agent_error , "answer" : {}}

    # skip summarization node
    if agent == SUMMARIZATION:
        return None

    answer = {}
    if "messages" in agent_data and agent_data["messages"]:
        answer["content"] = agent_data["messages"][-1].get("content")

    answer["tasks"] = reformat_subtasks(agent_data.get("subtasks"))

    if agent == SUPERVISOR:
        answer[NEXT] = agent_data.get(NEXT)
    else:
        if agent_data.get("subtasks"):
            pending_subtask = [
                subtask["assigned_to"]
                for subtask in agent_data.get("subtasks")
                if subtask["status"] == SubTaskStatus.PENDING
            ]
            if pending_subtask:
                answer[NEXT] = pending_subtask[0]
            else:
                answer[NEXT] = FINALIZER

    return {"agent": agent, "answer": answer, "error": agent_error}


def prepare_chunk_response(chunk: bytes) -> bytes | None:
    """Converts and prepares a final chunk response."""
    try:
        data = json.loads(chunk)
    except json.JSONDecodeError:
        logger.exception("Invalid JSON")
        return json.dumps(
            {"event": "unknown", "data": {"error": "Invalid JSON"}}
        ).encode()

    agent = next(iter(data.keys()), None)

    if not agent:
        logger.error(f"Agent {agent} is not found in the json data")
        return json.dumps(
            {"event": "unknown", "data": {"error": "No agent found"}}
        ).encode()

    agent_data = data[agent]
    if agent_data.get("messages"):
        last_agent = agent_data["messages"][-1].get("name")
        # skip all intermediate supervisor response
        if agent == SUPERVISOR and last_agent != PLANNER and last_agent != FINALIZER:
            return None

    new_data = process_response(data, agent)

    return (
        json.dumps(
            {
                "event": "agent_action",
                "data": new_data,
            }
        ).encode()
        if new_data
        else None
    )
