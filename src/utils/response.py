import json
from typing import Any

from agents.common.constants import PLANNER, K8S_AGENT, KYMA_AGENT, K8S_AGENT_TASK_DESCRIPTION, \
    KYMA_AGENT_TASK_DESCRIPTION, COMMON, COMMON_TASK_DESCRIPTION, SUMMARIZATION
from agents.k8s.agent import KubernetesAgent
from agents.supervisor.agent import SUPERVISOR
from utils.logging import get_logger

logger = get_logger(__name__)


def reformat_subtasks(subtasks: dict[str, Any]) -> list[dict[str, Any]]:
    tasks= []
    for subtask in subtasks:
        task = {}
        if subtask["assigned_to"] == K8S_AGENT :
            task["type"] = K8S_AGENT
            task["value"] = K8S_AGENT_TASK_DESCRIPTION
        if subtask["assigned_to"] == KYMA_AGENT :
            task["type"] = KYMA_AGENT
            task["value"] = KYMA_AGENT_TASK_DESCRIPTION
        if subtask["assigned_to"] == COMMON :
            task["type"] = COMMON
            task["value"] = COMMON_TASK_DESCRIPTION
        else :
            task["type"] = "Other"
            task["value"] = "Answering rest of the task"
        tasks.append(task)
    return tasks

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

        answer["tasks"] = reformat_subtasks(agent_data.get("subtasks"))

    return {"agent": agent, "answer": answer}


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

    # skip summarization node
    if agent == SUMMARIZATION:
        return None
    if not agent:
        logger.error(f"Agent {agent} is not found in the json data")
        return json.dumps(
            {"event": "unknown", "data": {"error": "No agent found"}}
        ).encode()

    new_data = process_response(data, agent)


    return json.dumps(
        {
            "event": "agent_action",
            "data": new_data,
        }
    ).encode()
