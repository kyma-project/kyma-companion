from typing import cast

from langchain_core.embeddings import Embeddings

from agents.common.agent import BaseAgent
from agents.k8s.constants import GRAPH_STEP_TIMEOUT_SECONDS
from agents.kyma.constants import KYMA_AGENT
from agents.kyma.prompts import KYMA_AGENT_PROMPT
from agents.kyma.state import KymaAgentState
from agents.kyma.tools.query import kyma_query_tool
from agents.kyma.tools.search import create_search_kyma_doc_tool
from utils.models.factory import IModel, ModelType


class KymaAgent(BaseAgent):
    """Kyma agent class."""

    def __init__(self, models: dict[str, IModel | Embeddings]):
        tools = [
            create_search_kyma_doc_tool(
                cast(Embeddings, models[ModelType.TEXT_EMBEDDING_3_LARGE])
            ),
            kyma_query_tool,
        ]
        super().__init__(
            KYMA_AGENT,
            models[ModelType.GPT4O],
            tools,
            KYMA_AGENT_PROMPT,
            KymaAgentState,
        )
        self.graph.step_timeout = GRAPH_STEP_TIMEOUT_SECONDS
