import json
from typing import Any

from langgraph.constants import END
from pydantic import BaseModel

from agents.common.constants import (
    TASKS,
    ANSWER,
    CONTENT,
    ERROR,
    ERROR_RESPONSE,
    STATUS,
    FINALIZER,
    GATEKEEPER,
    INITIAL_SUMMARIZATION,
    IS_FEEDBACK,
    NEXT,
    PLANNER,
    SUMMARIZATION,
    RESPONSE_THINKING,
    RESPONSE_FINALIZING
)
from agents.common.state import SubTaskStatus
from agents.supervisor.agent import SUPERVISOR
from utils.logging import get_logger

logger = get_logger(__name__)


class ChunkInfo(BaseModel):
    """Response model for extract_info_from_response_chunk."""

    error: str | None = None
    final_response: str | None = None
    status: str | None = None


PLANNING_TASK = {
    "task_id": 0,
    "task_name": "Planning your request...",
    "status": SubTaskStatus.PENDING,
    "agent": PLANNER,
}


def reformat_subtasks(subtasks: list[dict[Any, Any]]) -> list[dict[str, Any]]:
    """Reformat subtasks list for companion response"""

    tasks = []

    if subtasks:
        # Mark Planning Task completed
        PLANNING_TASK["status"] = SubTaskStatus.COMPLETED
        tasks.append(PLANNING_TASK)  # Add Planning task as first task
        for i, subtask in enumerate(subtasks, 1):
            task = {
                "task_id": i,
                "task_name": subtask["task_title"],
                "status": subtask["status"],
                "agent": subtask["assigned_to"],
            }

            tasks.append(task)
    return tasks


def handle_agent_error(agent_data: dict[str, Any], agent: str) -> tuple[str | None, dict[str, Any] | None]:
    """Handle agent error cases and return error message and response if applicable."""

    agent_error = None
    if "error" in agent_data and agent_data["error"]:
        agent_error = agent_data["error"]
        if agent in (SUMMARIZATION, INITIAL_SUMMARIZATION):
            # we don't show summarization node, but only error
            error_response = {
                "agent": None,
                "error": agent_error,
                "answer": {"content": "", "tasks": [], NEXT: END},
            }
            return agent_error, error_response

    return agent_error, None


def process_response(data: dict[str, Any], agent: str) -> dict[str, Any] | None:
    """Process agent data and return the last message only."""
    agent_data = data[agent]

    # Handle error cases
    agent_error, error_response = handle_agent_error(agent_data, agent)
    if error_response is not None:
        return error_response

    # skip summarization node
    if agent in (SUMMARIZATION, INITIAL_SUMMARIZATION):
        return None

    # send planing task, if request was forwarded to supervisor
    if agent == GATEKEEPER and agent_data.get(NEXT) == SUPERVISOR:
        # Mark Planning Task pending
        PLANNING_TASK["status"] = SubTaskStatus.PENDING
        return {
            "agent": GATEKEEPER,
            "error": None,
            "answer": {
                "content": "",
                "tasks": [PLANNING_TASK],
                IS_FEEDBACK: (agent_data.get(IS_FEEDBACK) if IS_FEEDBACK in agent_data else None),
                NEXT: SUPERVISOR,
            },
        }

    answer = {}
    if "messages" in agent_data and agent_data["messages"]:
        answer["content"] = agent_data["messages"][-1].get("content")
    answer["tasks"] = reformat_subtasks(agent_data.get("subtasks"))

    # assign NEXT
    # as of now 'next' field is provided by only SUPERVISOR and GATEKEEPER
    if agent in (SUPERVISOR, GATEKEEPER):
        answer[NEXT] = agent_data.get(NEXT)
        if IS_FEEDBACK in agent_data:
            answer[IS_FEEDBACK] = agent_data.get(IS_FEEDBACK)
    else:
        # for all other agent, decide next based on pending task
        if agent_data.get("subtasks"):
            # get pending subtasks
            pending_subtask = [
                subtask["assigned_to"]
                for subtask in agent_data.get("subtasks")
                if subtask["status"] == SubTaskStatus.PENDING
            ]
            # if subtask pending, assign Next to first pending task
            if pending_subtask:
                answer[NEXT] = pending_subtask[0]
            else:
                # if no pending task
                answer[NEXT] = FINALIZER

    return {"agent": agent, "answer": answer, "error": agent_error}


def prepare_chunk_response(chunk: bytes) -> bytes | None:
    """Converts and prepares a final chunk response."""
    try:
        data = json.loads(chunk)
    except json.JSONDecodeError:
        logger.exception("Invalid JSON")
        return json.dumps({"event": "unknown", "data": {"error": "Invalid JSON"}}).encode()

    agent = next(iter(data.keys()), None)

    if not agent:
        logger.error(f"Agent {agent} is not found in the json data")
        return json.dumps({"event": "unknown", "data": {"error": "No agent found"}}).encode()

    agent_data = data[agent]

    if agent == ERROR:
        return json.dumps(
            {
                "event": "unknown",
                "data": {
                    "agent": None,
                    "error": agent_data[ERROR],
                    "answer": {"content": agent_data[ERROR], "tasks": [], NEXT: END},
                },
            }
        ).encode()

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

def extract_info_from_response_chunk(chunk: str) -> ChunkInfo | None:
    """Extracts info from a response chunk. Returns ChunkInfo when successful, otherwise None."""
    try:
        data = json.loads(chunk)
    except json.JSONDecodeError:
        return ChunkInfo(error="Invalid JSON in chunk response")

    agent = next(iter(data.keys()), None)
    if not agent:
        logger.error(f"Agent {agent} is not found in the json data")
        return ChunkInfo(error="No agent found in the agent metadata")

    agent_data = data[agent]
    if agent == ERROR:
        return ChunkInfo(error=agent_data[ERROR])

    if agent_data.get("messages"):
        last_agent = agent_data["messages"][-1].get("name")
        # skip all intermediate supervisor response
        if agent == SUPERVISOR and last_agent != PLANNER and last_agent != FINALIZER:
            return None

    new_data = process_response(data, agent)
    if not new_data or not ANSWER in new_data or not new_data[ANSWER]:
        logger.exception(f"Failed to process response data: {data}")
        return None
    
    if ERROR in new_data and new_data[ERROR]:
        logger.error(f"Error in agent response: {new_data[ERROR]}")
        return ChunkInfo(error=new_data[ERROR])

    if NEXT in new_data[ANSWER] and new_data[ANSWER][NEXT] == END:
        if CONTENT in new_data[ANSWER] and new_data[ANSWER][CONTENT]:
            return ChunkInfo(final_response=new_data[ANSWER][CONTENT])
        else:
            return ChunkInfo(error=ERROR_RESPONSE)

    if TASKS in new_data[ANSWER] and new_data[ANSWER][TASKS] and len(new_data[ANSWER][TASKS]) > 0:
        tasks = new_data[ANSWER][TASKS]
        for task in tasks:
            if task.get(STATUS) != SubTaskStatus.COMPLETED:
                return ChunkInfo(status=task.get("task_name", RESPONSE_THINKING))
            
    if NEXT in new_data[ANSWER] and new_data[ANSWER][NEXT] == FINALIZER:
        return ChunkInfo(status=RESPONSE_FINALIZING)
            
    logger.exception(f"Failed to extract useful information from response data: {data}")
    return ChunkInfo(error=ERROR_RESPONSE)
