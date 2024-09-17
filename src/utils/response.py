import json

from agents.common.constants import EXIT


def prepare_chunk_response(chunk: bytes) -> bytes:
    """Converts and prepares a final chunk response."""
    data = json.loads(chunk)
    agent = next(iter(data.keys()))

    if EXIT in data:
        return json.dumps(
            {
                "event": "final_response",
                "data": {
                    "answer": data[EXIT]["final_response"],
                },
            }
        ).encode()

    return json.dumps(
        {
            "event": "agent_action",
            "data": {
                "agent": agent,
                "answer": data[agent],
            },
        }
    ).encode()
