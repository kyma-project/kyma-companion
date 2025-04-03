from unittest.mock import MagicMock

import pytest

from agents.k8s.agent import K8S_AGENT, KubernetesAgent
from agents.k8s.tools.logs import fetch_pod_logs_tool
from agents.k8s.tools.query import k8s_overview_query_tool, k8s_query_tool
from utils.models.factory import IModel, ModelType


@pytest.fixture
def mock_model():
    gpt40 = MagicMock(spec=IModel)
    gpt40.name = ModelType.GPT4O
    return gpt40


def test_kubernetes_agent_init(mock_model):
    """Test that KubernetesAgent initializes correctly with all expected attributes."""
    agent = KubernetesAgent(mock_model)

    # Verify the agent name
    assert agent.name == K8S_AGENT

    # Verify the model is set correctly
    assert agent.model == mock_model

    # Verify the tools are set correctly
    expected_tools = [k8s_query_tool, fetch_pod_logs_tool, k8s_overview_query_tool]
    assert agent.tools == expected_tools
