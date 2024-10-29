from agents.common.agent import BaseAgent
from agents.k8s.constants import GRAPH_STEP_TIMEOUT_SECONDS
from agents.kyma.constants import KYMA_AGENT
from agents.kyma.prompts import KYMA_AGENT_PROMPT
from agents.kyma.state import KymaAgentState
from agents.kyma.tools.query import kyma_query_tool
from agents.kyma.tools.search import search_kyma_doc_tool
from utils.models import IModel


class KymaAgent(BaseAgent):
    """Kyma agent class."""

    def __init__(self, model: IModel):
        tools = [search_kyma_doc_tool, kyma_query_tool]
        super().__init__(KYMA_AGENT, model, tools, KYMA_AGENT_PROMPT, KymaAgentState)
        self.graph.step_timeout = GRAPH_STEP_TIMEOUT_SECONDS
