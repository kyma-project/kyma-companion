import functools
from typing import Any

from langchain_core.tools import tool

from agents.common.state import AgentState
from agents.common.utils import agent_node, create_agent
from utils.logging import get_logger
from utils.models import Model

logger = get_logger(__name__)
KYMA_AGENT = "KymaAgent"


@tool
def search_kyma_doc(query: str) -> str:
    """Search Kyma documentation."""
    logger.info(f"Searching Kyma documentation for query: {query}")
    # TODO: Implement the actual search logic with RAG.
    return (
        "Kyma is an opinionated set of Kubernetes-based modular building blocks, including all necessary "
        "capabilities to develop and run enterprise-grade cloud-native applications."
    )


class KymaAgent:
    """Supervisor agent class."""

    name: str = KYMA_AGENT

    def __init__(self, model: Model):
        self.kyma_agent_node = functools.partial(
            agent_node,
            agent=create_agent(
                model.llm,
                [search_kyma_doc],
                "You are Kyma expert. You assist users with Kyma related questions.",
            ),
            name=KYMA_AGENT,
        )

    def agent_node(self, state: AgentState) -> dict[str, Any]:
        """Agent node."""

        return self.kyma_agent_node(state)
