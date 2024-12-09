from agents.common.agent import BaseAgent
from agents.common.constants import GRAPH_STEP_TIMEOUT_SECONDS, K8S_AGENT
from agents.k8s.prompts import K8S_AGENT_PROMPT
from agents.k8s.state import KubernetesAgentState
from agents.k8s.tools.logs import fetch_pod_logs_tool
from agents.k8s.tools.query import k8s_query_tool
from utils.models.factory import IModel


class KubernetesAgent(BaseAgent):
    """Kubernetes agent class."""

    def __init__(self, model: IModel):
        tools = [k8s_query_tool, fetch_pod_logs_tool]
        super().__init__(
            K8S_AGENT, model, tools, K8S_AGENT_PROMPT, KubernetesAgentState
        )
        self.graph.step_timeout = GRAPH_STEP_TIMEOUT_SECONDS
