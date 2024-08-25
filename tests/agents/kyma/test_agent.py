import functools
from unittest.mock import Mock, patch

import pytest
from langchain.agents import AgentExecutor

from agents.kyma.agent import KYMA_AGENT, KymaAgent


class TestKymaAgent:

    @pytest.fixture
    def kyma_agent(self):
        return KymaAgent(Mock())  # noqa

    @pytest.mark.parametrize(
        "create_agent_return, agent_node_return, expected_type, expected_name",
        [
            (
                Mock(spec=AgentExecutor),
                {"messages": [{"content": "kyma info", "type": "ai"}]},
                functools.partial,
                KYMA_AGENT,
            ),
            (
                Mock(spec=AgentExecutor),
                {"messages": []},
                functools.partial,
                KYMA_AGENT,
            ),
            (
                Mock(spec=AgentExecutor),
                {"messages": [{"content": "Error occurred", "type": "system"}]},
                functools.partial,
                KYMA_AGENT,
            ),
        ],
    )
    @patch("agents.kyma.agent.get_logger", Mock())
    @patch("agents.kyma.agent.create_agent")
    @patch("agents.kyma.agent.agent_node")
    def test_agent_node(
        self,
        mock_agent_node,
        mock_create_agent,
        kyma_agent,
        create_agent_return,
        agent_node_return,
        expected_type,
        expected_name,
    ):
        # Setup
        mock_create_agent.return_value = create_agent_return
        mock_agent_node.return_value = agent_node_return

        # Execute
        result = kyma_agent.agent_node()

        # Assert
        mock_create_agent.assert_called_once_with(
            kyma_agent.model.llm,
            [KymaAgent.search_kyma_doc],
            "You are Kyma expert. You assist users with Kyma related questions.",
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
            name=KYMA_AGENT,
        )
