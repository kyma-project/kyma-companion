from typing import cast

from langchain_core.embeddings import Embeddings
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import BaseTool

from agents.cluster_diagnostics.prompts import (
    CLUSTER_DIAGNOSTICS_AGENT_INSTRUCTIONS,
    CLUSTER_DIAGNOSTICS_AGENT_PROMPT,
)
from agents.cluster_diagnostics.state import ClusterDiagnosticsAgentState
from agents.cluster_diagnostics.tools.modules import fetch_non_ready_modules
from agents.cluster_diagnostics.tools.nodes import fetch_node_resources
from agents.cluster_diagnostics.tools.warnings import fetch_warning_events
from agents.common.agent import BaseAgent
from agents.common.constants import AGENT_MESSAGES, CLUSTER_DIAGNOSTICS_AGENT
from utils.models.factory import IModel
from utils.settings import GRAPH_STEP_TIMEOUT_SECONDS, MAIN_MODEL_MINI_NAME


class ClusterDiagnosticsAgent(BaseAgent):
    """Cluster diagnostics agent for cluster-scoped troubleshooting and health checks.

    Collects warning events, node resource usage, and Kyma module health data,
    then synthesizes a diagnostic report.
    """

    def __init__(self, models: dict[str, IModel | Embeddings]) -> None:
        tools: list[BaseTool] = [
            fetch_warning_events,
            fetch_node_resources,
            fetch_non_ready_modules,
        ]
        agent_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", CLUSTER_DIAGNOSTICS_AGENT_PROMPT),
                MessagesPlaceholder(variable_name=AGENT_MESSAGES),
                ("human", "{query}"),
                ("system", CLUSTER_DIAGNOSTICS_AGENT_INSTRUCTIONS),
            ]
        )
        super().__init__(
            name=CLUSTER_DIAGNOSTICS_AGENT,
            model=cast(IModel, models[MAIN_MODEL_MINI_NAME]),
            tools=tools,
            agent_prompt=agent_prompt,
            state_class=ClusterDiagnosticsAgentState,
        )
        self.graph.step_timeout = GRAPH_STEP_TIMEOUT_SECONDS
