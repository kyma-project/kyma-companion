import json

from agents.common.constants import EXIT


def prepare_chunk_response(chunk: bytes) -> str:
    """Prepare a chunk response in ndjson format."""

    # TODO: don't add supervisor and finalizer actions
    # TODO: convert SubTasks part of planner response to JSON

    data = json.loads(chunk)
    agent = list(data.keys())[0]

    if EXIT in data:
        return json.dumps(
            {
                "event": "final_response",
                "data": {
                    "answer": data[EXIT]["final_response"],
                },
            }
        )

    return json.dumps(
        {
            "event": "agent_action",
            "data": {
                "agent": agent,
                "answer": data[agent],
            },
        }
    )
