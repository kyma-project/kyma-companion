from typing import cast

from langchain_core.embeddings import Embeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool

from agents.common.agent import BaseAgent
from agents.common.constants import (
    AGENT_MESSAGES,
    KYMA_AGENT,
)
from agents.k8s.tools.logs import fetch_pod_logs_tool
from agents.kyma.prompts import KYMA_AGENT_INSTRUCTIONS, KYMA_AGENT_PROMPT
from agents.kyma.state import KymaAgentState
from agents.kyma.tools.query import cluster_query_tool, fetch_kyma_resource_version
from agents.kyma.tools.search import SearchKymaDocTool
from utils.models.factory import IModel
from utils.settings import GRAPH_STEP_TIMEOUT_SECONDS, MAIN_MODEL_NAME


class KymaAgent(BaseAgent):
    """Kyma agent handling Kyma, Kubernetes, and SAP BTP related queries.

    This agent is equipped with tools for searching Kyma documentation, querying
    cluster resources (both Kyma and Kubernetes), and fetching pod logs.
    """

    def __init__(self, models: dict[str, IModel | Embeddings]) -> None:
        """Initialize the KymaAgent with all tools and models."""
        tools: list[BaseTool] = [
            fetch_kyma_resource_version,
            cluster_query_tool,
            SearchKymaDocTool(models),
            fetch_pod_logs_tool,
        ]
        agent_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", KYMA_AGENT_PROMPT),
                MessagesPlaceholder(variable_name=AGENT_MESSAGES),
                ("human", "{query}"),
                ("system", KYMA_AGENT_INSTRUCTIONS),
            ]
        )
        super().__init__(
            name=KYMA_AGENT,
            model=cast(IModel, models[MAIN_MODEL_NAME]),
            tools=tools,
            agent_prompt=agent_prompt,
            state_class=KymaAgentState,
        )
        self.graph.step_timeout = GRAPH_STEP_TIMEOUT_SECONDS
