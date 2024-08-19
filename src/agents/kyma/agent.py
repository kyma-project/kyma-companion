import functools

from langchain_core.tools import tool

from agents.common.utils import agent_node, create_agent
from utils.logging import get_logger
from utils.models import LLM, ModelFactory

logger = get_logger(__name__)

model_factory = ModelFactory()
model = model_factory.create_model(LLM.GPT4O_MODEL)

KYMA_AGENT_NAME = "KymaAgent"


@tool
def search_kyma_doc(query: str) -> str:
    """Search Kyma documentation."""
    logger.info(f"Searching Kyma documentation for query: {query}")
    # TODO: Implement the actual search logic with RAG.
    return (
        "Kyma is an opinionated set of Kubernetes-based modular building blocks, including all necessary "
        "capabilities to develop and run enterprise-grade cloud-native applications."
    )


kyma_agent_node = functools.partial(
    agent_node,
    agent=create_agent(
        model.llm,
        [search_kyma_doc],
        "You are Kyma expert. You assist users with Kyma related questions.",
    ),
    name=KYMA_AGENT_NAME,
)
