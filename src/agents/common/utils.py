"""Common utility functions for agents."""

import ast
import json
from collections.abc import Sequence
from typing import Any

import tiktoken
import yaml
from langchain_core.messages import (
    BaseMessage,
    ToolMessage,
)

from agents.common.constants import (
    CLUSTER,
    RECENT_MESSAGES_LIMIT,
)
from agents.common.data import Message
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
    """
    filtered = messages[-recent_message_limit:]
    # remove the tool messages from head of the list,
    # because a tool message must be preceded by a system message.
    for i, message in enumerate(filtered):
        if not isinstance(message, ToolMessage):
            return filtered[i:]
    return filtered


def compute_string_token_count(text: str, model_type: str) -> int:
    """Returns the token count of the string."""
    try:
        encoding = tiktoken.encoding_for_model(model_type)
    except KeyError:
        logger.warning(f"Model '{model_type}' not recognized by tiktoken, using cl100k_base encoding")
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text=text))


async def get_relevant_context_from_k8s_cluster(message: Message, k8s_client: IK8sClient) -> str:
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
        logger.info("Fetching all not running Pods, Node metrics, and K8s Events with warning type")
        pods = yaml.dump_all(await k8s_client.list_not_running_pods(namespace=namespace))
        metrics = yaml.dump_all(await k8s_client.list_nodes_metrics())
        events = yaml.dump_all(await k8s_client.list_k8s_warning_events(namespace=namespace))

        context = f"{pods}\n{metrics}\n{events}"

    elif is_non_empty_str(namespace) and kind.lower() == "namespace":
        # Get an overview of the namespace
        # by fetching all K8s events with warning type.
        logger.debug("Fetching all K8s Events with warning type")
        context = yaml.dump_all(await k8s_client.list_k8s_warning_events(namespace=namespace))

    elif is_non_empty_str(kind) and is_non_empty_str(api_version):
        # Describe a specific resource.
        logger.info(f"Fetching all entities of Kind {kind} with API version {api_version}")
        resources = yaml.dump(
            await k8s_client.describe_resource(
                api_version=api_version,
                kind=kind,
                name=name,
                namespace=namespace,
            )
        )
        events = yaml.dump_all(
            await k8s_client.list_k8s_events_for_resource(
                kind=kind,
                name=name,
                namespace=namespace,
            )
        )

        context = f"{resources}\n{events}"

    else:
        raise Exception("Invalid message provided.")

    # Note: k8s_client methods already sanitize data internally.
    # No additional sanitization needed here (fixes double-sanitization bug).

    return context


def convert_string_to_object(input_string: str) -> Any:
    """Try to convert string to object."""
    try:
        return json.loads(input_string)
    except Exception:
        try:
            return ast.literal_eval(input_string)
        except (SyntaxError, ValueError):
            return input_string
