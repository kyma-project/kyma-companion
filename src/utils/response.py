import json
from typing import Any

from agents.common.constants import EXIT, PLANNER
from agents.supervisor.agent import SUPERVISOR
from utils.logging import get_logger

logger = get_logger(__name__)


def process_response(data: dict[str, Any], agent: str) -> dict[str, Any]:
    """Process agent data and return the last message only."""
    agent_data = data[agent]

    if "error" in agent_data and agent_data["error"]:
        return {"agent": agent, "error": agent_data["error"]}

    answer = {}
    if "messages" in agent_data and agent_data["messages"]:
        answer["content"] = agent_data["messages"][-1].get("content")

    if agent == PLANNER:
        answer["subtasks"] = agent_data.get("subtasks")

    if agent == SUPERVISOR:
        answer["next"] = agent_data.get("next")

    return {"agent": agent, "answer": answer}


def prepare_chunk_response(chunk: bytes) -> bytes:
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

    if agent == EXIT:
        response = {
            "event": "final_response",
            "data": (
                {"error": data[EXIT].get("error")}
                if data[EXIT].get("error")
                else {
                    "answer": {
                        "content": data[EXIT].get("final_response"),
                    }
                }
            ),
        }
        return json.dumps(response).encode()

    new_data = process_response(data, agent)

    return json.dumps(
        {
            "event": "agent_action",
            "data": new_data,
        }
    ).encode()
