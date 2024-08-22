import functools
from typing import Any

from langchain_core.tools import tool

from agents.common.state import AgentState
from agents.common.utils import agent_node, create_agent
from utils.logging import get_logger
from utils.models import Model

logger = get_logger(__name__)

K8S_AGENT = "KubernetesAgent"


@tool
def search_kubernetes_doc(query: str) -> str:
    """Search Kubernetes documentation."""
    logger.info(f"Searching Kubernetes documentation for query: {query}")
    # TODO: Implement the actual search logic with RAG.
    return (
        "Kubernetes, often abbreviated as K8s, is an open-source system designed to automate the deployment, "
        "scaling, and management of containerized applications. It acts as a powerful container orchestration "
        "platform, simplifying many of the complex tasks associated with running applications across a cluster of "
        "machines."
    )


class KubernetesAgent:
    """Supervisor agent class."""

    name: str = K8S_AGENT

    def __init__(self, model: Model):
        self.k8s_agent_node = functools.partial(
            agent_node,
            agent=create_agent(
                model.llm,
                [search_kubernetes_doc],
                "You are Kubernetes expert. You assist users with Kubernetes related questions.",
            ),
            name=K8S_AGENT,
        )

    def agent_node(self, state: AgentState) -> dict[str, Any]:
        """Agent node."""

        return self.k8s_agent_node(state)
