from langchain_core.embeddings import Embeddings

from agents.common.agent import BaseAgent
from agents.common.constants import GRAPH_STEP_TIMEOUT_SECONDS, KYMA_AGENT
from agents.kyma.prompts import KYMA_AGENT_PROMPT
from agents.kyma.state import KymaAgentState
from agents.kyma.tools.query import kyma_query_tool
from agents.kyma.tools.search import SearchKymaDocTool
from utils.models.factory import IModel, ModelType


class KymaAgent(BaseAgent):
    """Kyma agent class."""

    def __init__(self, models: dict[str, IModel | Embeddings]):
        tools = [
            SearchKymaDocTool(models),
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
