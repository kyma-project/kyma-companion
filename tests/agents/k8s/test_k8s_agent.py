import functools
from unittest.mock import Mock, patch

import pytest
from langchain.agents import AgentExecutor

from agents.k8s.agent import K8S_AGENT, KubernetesAgent
from agents.k8s.prompts import K8S_AGENT_PROMPT


class TestKubernetesAgent:

    @pytest.fixture
    def kubernetes_agent(self):
        return KubernetesAgent(Mock())  # noqa

    @pytest.mark.parametrize(
        "create_agent_return, agent_node_return, expected_type, expected_name",
        [
            (
                Mock(spec=AgentExecutor),
                {"messages": [{"content": "Kubernetes info", "type": "ai"}]},
                functools.partial,
                K8S_AGENT,
            ),
            (
                Mock(spec=AgentExecutor),
                {"messages": []},
                functools.partial,
                K8S_AGENT,
            ),
            (
                Mock(spec=AgentExecutor),
                {"messages": [{"content": "Error occurred", "type": "system"}]},
                functools.partial,
                K8S_AGENT,
            ),
        ],
    )
    @patch("agents.k8s.agent.get_logger", Mock())
    @patch("agents.k8s.agent.create_agent")
    @patch("agents.k8s.agent.agent_node")
    def test_agent_node(
        self,
        mock_agent_node,
        mock_create_agent,
        kubernetes_agent,
        create_agent_return,
        agent_node_return,
        expected_type,
        expected_name,
    ):
        # Setup
        mock_create_agent.return_value = create_agent_return
        mock_agent_node.return_value = agent_node_return

        # Execute
        result = kubernetes_agent.agent_node()

        # Assert
        mock_create_agent.assert_called_once_with(
            kubernetes_agent.model.llm,
            [KubernetesAgent.search_kubernetes_doc],
            K8S_AGENT_PROMPT,
        )

        assert isinstance(result, expected_type)
        assert result.func == mock_agent_node
        assert result.keywords["agent"] == create_agent_return
        assert result.keywords["name"] == expected_name

        # Verify that the returned partial function works as expected
        partial_result = result()
        assert partial_result == agent_node_return
        mock_agent_node.assert_called_once_with(
            agent=create_agent_return,
            name=K8S_AGENT,
        )
