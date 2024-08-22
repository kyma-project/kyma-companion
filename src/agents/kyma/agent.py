import functools

from langchain_core.tools import tool

from agents.common.utils import agent_node, create_agent
from utils.logging import get_logger
from utils.models import Model

logger = get_logger(__name__)
KYMA_AGENT = "KymaAgent"


class KymaAgent:
    """Supervisor agent class."""

    _name: str = KYMA_AGENT

    def __init__(self, model: Model):
        self.model = model

    @staticmethod
    @tool
    def search_kyma_doc(query: str) -> str:
        """Search Kyma documentation."""
        logger.info(f"Searching Kyma documentation for query: {query}")
        # TODO: Implement the actual search logic with RAG.
        return (
            "Kyma is an opinionated set of Kubernetes-based modular building blocks, including all necessary "
            "capabilities to develop and run enterprise-grade cloud-native applications."
        )

    @property
    def name(self) -> str:
        """Agent name."""
        return self._name

    def agent_node(self):  # noqa ANN
        """Get Kyma agent node function."""
        kyma_agent_node = create_agent(
            self.model.llm,
            [self.search_kyma_doc],
            "You are Kyma expert. You assist users with Kyma related questions.",
        )
        return functools.partial(
            agent_node,
            agent=kyma_agent_node,
            name=KYMA_AGENT,
        )
