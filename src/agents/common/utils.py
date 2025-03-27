from collections.abc import Sequence
from typing import Any

import tiktoken
from langchain_core.messages import BaseMessage, ToolMessage
from langgraph.constants import END
from langgraph.graph.message import Messages
from pydantic import BaseModel

from agents.common.constants import (
    CONTINUE,
    ERROR,
    MESSAGES,
    NEXT,
    RECENT_MESSAGES_LIMIT,
    SUBTASKS,
)
from agents.common.state import SubTask
from utils.logging import get_logger
from utils.models.factory import ModelType

logger = get_logger(__name__)


def filter_messages(
    messages: Sequence[BaseMessage],
    recent_message_limit: int = RECENT_MESSAGES_LIMIT,
) -> Sequence[BaseMessage]:
    """
    Filter the last n number of messages given last_messages_number.
    Args:
        messages: list of messages
        recent_message_limit:  int: number of last messages to return, default is 10

    Returns: list of last messages
    """
    filtered = messages[-recent_message_limit:]
    # remove the tool messages from head of the list,
    # because a tool message must be preceded by a system message.
    for i, message in enumerate(filtered):
        if not isinstance(message, ToolMessage):
            return filtered[i:]
    return filtered


def create_node_output(
    message: BaseMessage | None = None,
    next: str | None = None,
    subtasks: list[SubTask] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """
    This function is used to create the output of a LangGraph node centrally.

    Args:
        message: BaseMessage | None: message to be sent to the user
        next: str | None: next LangGraph node to be called
        subtasks: list[SubTask] | None: different steps/subtasks to follow
        final_response: str | None: final response to the user
        error: str | None: error message if error occurred
    """
    return {
        MESSAGES: [message] if message else [],
        NEXT: next,
        SUBTASKS: subtasks,
        ERROR: error,
    }


def compute_string_token_count(text: str, model_type: ModelType) -> int:
    """Returns the token count of the string."""
    return len(tiktoken.encoding_for_model(model_type).encode(text=text))


def compute_messages_token_count(msgs: Messages, model_type: ModelType) -> int:
    """Returns the token count of the messages."""
    tokens_per_msg = (
        compute_string_token_count(str(msg.content), model_type) for msg in msgs
    )
    return sum(tokens_per_msg)


def should_continue(state: BaseModel) -> str:
    """
    Returns END if there is an error, else CONTINUE.
    """
    if hasattr(state, "error") and state.error:
        return END
    return CONTINUE


def filter_k8s_data(k8s_data: dict) -> dict[str, Any] | None:
    """
    Filter Kubernetes data by removing managedFields and filtering out based on status.
    """

    # Create a deep copy to avoid modifying the original data
    filtered_data = k8s_data.copy()

    # Remove managedFields from metadata
    if "metadata" in filtered_data:
        filtered_data["metadata"].pop("managedFields", None)

    # Resource Type - Pods
    # Check if the pod is not in 'Running' phase
    if filtered_data.get("status", {}).get("phase", "").lower() != "running":
        return filtered_data

    # TODO
    # We need to implement different scenario for each resource type

    # Return None if the pod is in 'Running' phase
    return None


def filter_kyma_data(kyma_data: dict) -> dict[str, Any] | None:
    """
    Filter Kyma data by removing managedFields and filtering out based on status.
    """

    # Create a deep copy to avoid modifying the original data
    filtered_data = kyma_data.copy()

    # Remove managedFields from metadata
    if "metadata" in filtered_data:
        filtered_data["metadata"].pop("managedFields", None)

    # Resource Type - APIStatusRule
    # Check if the APIRuleStatus is not in 'OK' status
    if (
        filtered_data.get("status", {}).get("APIRuleStatus", {}).get("code", "").lower()
        != "ok"
    ):
        return filtered_data

    # TODO
    # We need to implement different scenario for each resource type

    # Return None if in 'OK' status
    return None
