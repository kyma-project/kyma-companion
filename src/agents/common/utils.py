import ast
import json
from http import HTTPStatus
from typing import Any

import tiktoken
import yaml

from agents.common.constants import CLUSTER
from agents.common.data import Message
from services.k8s import IK8sClient
from utils.exceptions import K8sClientError
from utils.logging import get_logger
from utils.utils import is_empty_str, is_non_empty_str

logger = get_logger(__name__)


def compute_string_token_count(text: str, model_type: str) -> int:
    """Returns the token count of the string."""
    try:
        encoding = tiktoken.encoding_for_model(model_type)
    except KeyError:
        logger.warning(f"Model '{model_type}' not recognized by tiktoken, using cl100k_base encoding")
        # "cl100k_base" is used by the tiktoken library for many OpenAI models.
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text=text))


def compute_messages_token_count(msgs: Any, model_type: str) -> int:
    """Returns the token count of the messages."""
    tokens_per_msg = (compute_string_token_count(str(msg.content), model_type) for msg in msgs)
    return sum(tokens_per_msg)


async def get_relevant_context_from_k8s_cluster(message: Message, k8s_client: IK8sClient) -> str:
    """Fetch the relevant data from Kubernetes cluster based on specified K8s resource in message."""

    logger.debug("Fetching relevant data from k8s cluster")

    namespace: str = message.namespace or ""
    kind: str = message.resource_kind or ""
    name: str = message.resource_name or ""
    api_version: str = message.resource_api_version or ""

    context = ""

    if is_empty_str(namespace) and kind.lower() == CLUSTER:
        logger.info("Fetching all not running Pods, Node metrics, and K8s Events with warning type")
        not_running_pods = k8s_client.list_not_running_pods(namespace=namespace)
        node_metrics = await k8s_client.list_nodes_metrics()
        warning_events = k8s_client.list_k8s_warning_events(namespace=namespace)

        pods_section = (
            yaml.dump_all(not_running_pods) if not_running_pods else "No non-running pods were found in the cluster."
        )
        metrics_section = (
            yaml.dump_all(node_metrics) if node_metrics else "No node metrics are available for the cluster."
        )
        events_section = (
            yaml.dump_all(warning_events) if warning_events else "No warning or error events were found in the cluster."
        )

        context = f"{pods_section}\n{metrics_section}\n{events_section}"

    elif is_non_empty_str(namespace) and kind.lower() == "namespace":
        logger.debug(f"Verifying that namespace '{namespace}' exists")
        try:
            await k8s_client.get_namespace(namespace)
            namespace_exists = True
        except K8sClientError as e:
            if e.status_code == HTTPStatus.NOT_FOUND:
                namespace_exists = False
            else:
                raise

        if not namespace_exists:
            context = f"Namespace '{namespace}' was not found in the cluster."
        else:
            logger.debug("Fetching all K8s Events with warning type")
            warning_events = k8s_client.list_k8s_warning_events(namespace=namespace)
            context = (
                yaml.dump_all(warning_events)
                if warning_events
                else f"Namespace '{namespace}' exists, but no warning or error events were found."
            )

    elif is_non_empty_str(kind) and is_non_empty_str(api_version):
        logger.info(f"Fetching all entities of Kind {kind} with API version {api_version}")
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
    data_sanitizer = k8s_client.get_data_sanitizer()
    if data_sanitizer:
        context = str(data_sanitizer.sanitize(context))

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
