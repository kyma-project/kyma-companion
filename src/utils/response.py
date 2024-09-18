import json
from typing import Any

from agents.common.constants import EXIT
from utils.logging import get_logger

logger = get_logger(__name__)


def extract_message_content(message: dict[str, Any]) -> dict[str, str]:
    """Extract the content field from a message, handling potential missing keys."""
    return {"content": message.get("content", "")}


def process_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Process a list of messages, extracting only the content field."""
    return [extract_message_content(message) for message in messages]


def prepare_chunk_response(chunk: bytes) -> bytes:
    """Converts and prepares a final chunk response."""
    try:
        data = json.loads(chunk)
    except json.JSONDecodeError:
        logger.exception("Invalid JSON")
        return json.dumps(
            {"event": "error", "data": {"message": "Invalid JSON"}}
        ).encode()

    agent = next(iter(data.keys()), None)
    if not agent:
        logger.exception(f"Agent {agent} is not found in the json data")
        return json.dumps(
            {"event": "error", "data": {"message": "No agent found"}}
        ).encode()

    if agent == EXIT:
        return json.dumps(
            {
                "event": "final_response",
                "data": {
                    "answer": data[EXIT].get("final_response", ""),
                },
            }
        ).encode()

    agent_data = data[agent]
    if isinstance(agent_data, dict) and "messages" in agent_data:
        agent_data["messages"] = process_messages(agent_data["messages"])

    return json.dumps(
        {
            "event": "agent_action",
            "data": {
                "agent": agent,
                "answer": agent_data,
            },
        }
    ).encode()
