from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from agents.common.agent import BaseAgent
from agents.common.constants import (
    AGENT_MESSAGES,
    GRAPH_STEP_TIMEOUT_SECONDS,
    K8S_AGENT,
)
from agents.k8s.prompts import K8S_AGENT_PROMPT
from agents.k8s.state import KubernetesAgentState
from agents.k8s.tools.logs import fetch_pod_logs_tool
from agents.k8s.tools.query import k8s_query_tool, k8s_overview_query_tool
from utils.models.factory import IModel


class KubernetesAgent(BaseAgent):
    """Kubernetes agent class."""

    def __init__(self, model: IModel):
        tools = [k8s_query_tool, fetch_pod_logs_tool, k8s_overview_query_tool]
        agent_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", K8S_AGENT_PROMPT),
                MessagesPlaceholder(variable_name=AGENT_MESSAGES),
                ("human", "{query}"),
            ]
        )
        super().__init__(
            name=K8S_AGENT,
            model=model,
            tools=tools,
            agent_prompt=agent_prompt,
            state_class=KubernetesAgentState,
        )
        self.graph.step_timeout = GRAPH_STEP_TIMEOUT_SECONDS
