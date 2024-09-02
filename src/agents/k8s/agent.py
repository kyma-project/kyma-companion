import functools

from langchain_core.tools import tool

from agents.common.utils import agent_node, create_agent
from agents.k8s.prompts import K8S_AGENT_PROMPT
from utils.logging import get_logger
from utils.models import IModel

logger = get_logger(__name__)

K8S_AGENT = "KubernetesAgent"


class KubernetesAgent:
    """Supervisor agent class."""

    _name: str = K8S_AGENT

    @staticmethod
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

    def __init__(self, model: IModel):
        self.model = model

    @property
    def name(self) -> str:
        """Agent name."""
        return self._name

    def agent_node(self):  # noqa ANN
        """Get Kubernetes agent node function."""
        k8s_agent_node = create_agent(
            self.model.llm,
            [self.search_kubernetes_doc],
            K8S_AGENT_PROMPT,
        )
        return functools.partial(
            agent_node,
            agent=k8s_agent_node,
            name=K8S_AGENT,
        )
