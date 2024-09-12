import json
from unittest.mock import Mock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from agents.common.constants import COMMON, EXIT
from agents.common.state import AgentState, SubTask
from agents.common.utils import filter_messages
from agents.k8s.agent import K8S_AGENT
from agents.kyma.agent import KYMA_AGENT
from agents.supervisor.agent import FINALIZER, SupervisorAgent


class TestSupervisorAgent:

    @pytest.fixture
    def supervisor_agent(self):
        agent = SupervisorAgent(Mock(), [K8S_AGENT, KYMA_AGENT, COMMON])  # noqa
        agent.supervisor_chain = Mock()
        return agent  # noqa

    @pytest.mark.parametrize(
        "mock_supervisor_chain_invoke_return, subtasks, messages, expected_next, expected_subtasks, expected_error",
        [
            (
                AIMessage(content=f"""{{"next": "{K8S_AGENT}"}}"""),
                [
                    SubTask(
                        description="Task 1", assigned_to=K8S_AGENT, status="pending"
                    ),
                    SubTask(
                        description="Task 2", assigned_to=KYMA_AGENT, status="pending"
                    ),
                ],
                [
                    HumanMessage(content="Test message 1"),
                    AIMessage(content="Test message 2"),
                ],
                K8S_AGENT,
                [
                    SubTask(
                        description="Task 1", assigned_to=K8S_AGENT, status="pending"
                    ),
                    SubTask(
                        description="Task 2", assigned_to=KYMA_AGENT, status="pending"
                    ),
                ],
                None,
            ),
            (
                AIMessage(content=f"""{{"next": "{KYMA_AGENT}"}}"""),
                [
                    SubTask(
                        description="Task 2",
                        assigned_to=KYMA_AGENT,
                        status="in_progress",
                    )
                ],
                [AIMessage(content="Fake message")],
                KYMA_AGENT,
                [
                    SubTask(
                        description="Task 2",
                        assigned_to=KYMA_AGENT,
                        status="in_progress",
                    )
                ],
                None,
            ),
            (
                AIMessage(content=f"""{{"next": "{FINALIZER}"}}"""),
                [
                    SubTask(
                        description="Task 3", assigned_to=K8S_AGENT, status="completed"
                    )
                ],
                [],
                FINALIZER,
                [
                    SubTask(
                        description="Task 3", assigned_to=K8S_AGENT, status="completed"
                    )
                ],
                None,
            ),
            (
                Exception("Test error"),
                [
                    SubTask(
                        description="Task 4", assigned_to=KYMA_AGENT, status="pending"
                    )
                ],
                [HumanMessage(content="Error test")],
                EXIT,
                [
                    SubTask(
                        description="Task 4", assigned_to=KYMA_AGENT, status="pending"
                    )
                ],
                "Test error",
            ),
        ],
    )
    @patch("agents.k8s.agent.get_logger", Mock())
    def test_agent_node(
        self,
        supervisor_agent,
        mock_supervisor_chain_invoke_return,
        subtasks,
        messages,
        expected_next,
        expected_subtasks,
        expected_error,
    ):
        # Setup
        if isinstance(mock_supervisor_chain_invoke_return, Exception):
            supervisor_agent.supervisor_chain.invoke = Mock(
                side_effect=mock_supervisor_chain_invoke_return
            )
        else:
            supervisor_agent.supervisor_chain.invoke = Mock(
                return_value=mock_supervisor_chain_invoke_return
            )

        state = AgentState(messages=messages, subtasks=subtasks)

        # Execute
        supervisor_node = supervisor_agent.agent_node()
        result = supervisor_node(state)

        # Assert
        supervisor_agent.supervisor_chain.invoke.assert_called_once_with(
            input={
                "messages": filter_messages(messages),
                "subtasks": json.dumps([subtask.dict() for subtask in subtasks]),
            }
        )

        assert result["next"] == expected_next
        if expected_error:
            assert result["error"] == expected_error
        else:
            assert "error" not in result
