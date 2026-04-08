import json
from typing import Any

from langgraph.constants import END

from agents.common.constants import (
    ERROR,
    GATEKEEPER,
    KYMA_AGENT,
    NEXT,
)
from utils.logging import get_logger

logger = get_logger(__name__)


def handle_agent_error(agent_data: dict[str, Any], agent: str) -> tuple[str | None, dict[str, Any] | None]:
    """Handle agent error cases and return error message and response if applicable."""

    agent_error = None
    if "error" in agent_data and agent_data["error"]:
        agent_error = agent_data["error"]
    return agent_error, None


def process_response(data: dict[str, Any], agent: str) -> dict[str, Any] | None:
    """Process agent data and return the last message only."""
    agent_data = data[agent]

    agent_error, error_response = handle_agent_error(agent_data, agent)
    if error_response is not None:
        return error_response

    answer: dict[str, Any] = {}
    if "messages" in agent_data and agent_data["messages"]:
        answer["content"] = agent_data["messages"][-1].get("content")

    answer["tasks"] = []

    if agent == GATEKEEPER:
        answer[NEXT] = agent_data.get(NEXT)
    else:
        answer[NEXT] = END

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
                    "answer": {"content": agent_data[ERROR], NEXT: END},
                },
            }
        ).encode()

    # Skip intermediate KymaAgent output; the Finalizer produces the user-facing response.
    if agent == KYMA_AGENT:
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
