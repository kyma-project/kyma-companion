import ast
import json
from collections.abc import Sequence
from typing import Any

import tiktoken
import yaml
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.constants import END
from langgraph.graph.message import Messages
from pydantic import BaseModel

from agents.common.constants import (
    CLUSTER,
    CONTINUE,
    ERROR,
    MESSAGES,
    NEXT,
    RECENT_MESSAGES_LIMIT,
    SUBTASKS,
    UNKNOWN,
)
from agents.common.data import Message
from agents.common.state import SubTask, UserInput
from services.k8s import IK8sClient
from utils.logging import get_logger
from utils.utils import is_empty_str, is_non_empty_str

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


def filter_valid_messages(
    messages: Sequence[BaseMessage] | list[BaseMessage],
) -> list[BaseMessage]:
    """
    Filters the invalid sequence of messages.
    For example:
    - An assistant message with 'tool_calls' must be followed by tool messages responding to each 'tool_call_id'.
    - A tool message must be preceded by an assistant message with 'tool_calls'.
    This method should be used when the LLMs are being invoked with messages.
    """

    filtered: list[BaseMessage] = []
    for i, message in enumerate(messages):
        if isinstance(message, AIMessage) and message.tool_calls:
            # check if the next messages are tool calls as requested by AIMessage.
            tool_call_count = len(message.tool_calls)
            next_messages = messages[
                i + 1 : i + 1 + tool_call_count
            ]  # +1 because the index starts from zero.
            if len(next_messages) == tool_call_count and all(
                isinstance(msg, ToolMessage) for msg in next_messages
            ):
                # Append the AIMessage and its corresponding ToolMessages.
                filtered.append(message)
                filtered.extend(next_messages)
        elif not isinstance(message, ToolMessage):
            # append other valid messages.
            # ToolMessage should not be added directly.
            # It should be preceded by an AIMessage with tool_calls.
            filtered.append(message)
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


def compute_string_token_count(text: str, model_type: str) -> int:
    """Returns the token count of the string."""
    try:
        encoding = tiktoken.encoding_for_model(model_type)
    except KeyError:
        logger.warning(
            f"Model '{model_type}' not recognized by tiktoken, using cl100k_base encoding"
        )
        # "cl100k_base" is used by the tiktoken library for many OpenAI models.
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text=text))


def compute_messages_token_count(msgs: Messages, model_type: str) -> int:
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


def get_resource_context_message(user_input: UserInput) -> SystemMessage | None:
    """Get the resource context message based on the user input."""
    if user_input.resource_kind == UNKNOWN:
        return SystemMessage(
            content="Resource information is not available. "
            "Ask the user, if you need resource information like kind, name or namespace."
        )

    resource_context = user_input.get_resource_information()
    if resource_context and len(resource_context) > 0:
        return SystemMessage(content=str(resource_context))

    return None


async def get_relevant_context_from_k8s_cluster(
    message: Message, k8s_client: IK8sClient
) -> str:
    """Fetch the relevant data from Kubernetes cluster based on specified K8s resource in message."""

    logger.debug("Fetching relevant data from k8s cluster")

    namespace: str = message.namespace or ""
    kind: str = message.resource_kind or ""
    name: str = message.resource_name or ""
    api_version: str = message.resource_api_version or ""

    # Query the Kubernetes API to get the context.
    context = ""

    if is_empty_str(namespace) and kind.lower() == CLUSTER:
        # Get an overview of the cluster
        # by fetching all not running pods, all K8s Nodes metrics,
        # and all K8s events with warning type.
        logger.info(
            "Fetching all not running Pods, Node metrics, and K8s Events with warning type"
        )
        pods = yaml.dump_all(k8s_client.list_not_running_pods(namespace=namespace))
        metrics = yaml.dump_all(await k8s_client.list_nodes_metrics())
        events = yaml.dump_all(k8s_client.list_k8s_warning_events(namespace=namespace))

        context = f"{pods}\n{metrics}\n{events}"

    elif is_non_empty_str(namespace) and kind.lower() == "namespace":
        # Get an overview of the namespace
        # by fetching all K8s events with warning type.
        logger.debug("Fetching all K8s Events with warning type")
        context = yaml.dump_all(k8s_client.list_k8s_warning_events(namespace=namespace))

    elif is_non_empty_str(kind) and is_non_empty_str(api_version):
        # Describe a specific resource. Not-namespaced resources need the namespace
        # field to be empty. Finally, get all events related to given resource.
        logger.info(
            f"Fetching all entities of Kind {kind} with API version {api_version}"
        )
        resources = yaml.dump(
            k8s_client.describe_resource(
                api_version=api_version,
                kind=kind,
                name=name,
                namespace=namespace,
            )
        )
        events = yaml.dump_all(
            k8s_client.list_k8s_events_for_resource(
                kind=kind,
                name=name,
                namespace=namespace,
            )
        )

        context = f"{resources}\n{events}"

    else:
        raise Exception("Invalid message provided.")

    return context


def convert_string_to_object(input_string: str) -> Any:
    """Try to convert string to object."""
    # First, try using json.loads (works for proper JSON strings)
    try:
        return json.loads(input_string)
    except Exception:
        # If JSON parsing fails
        try:
            return ast.literal_eval(input_string)
        except (SyntaxError, ValueError):
            # If it's not valid JSON or a Python literal, return the string itself
            return input_string
