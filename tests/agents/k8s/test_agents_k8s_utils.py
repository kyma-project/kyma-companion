from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from agents.common.state import SubTask
from agents.k8s.constants import K8S_AGENT
from agents.k8s.state import KubernetesAgentState
from agents.k8s.utils import agent_edge, subtask_selector_edge
from services.k8s import IK8sClient


@pytest.mark.parametrize(
    "is_last_step, my_task, expected_output",
    [
        (
            False,
            SubTask(description="test", assigned_to=K8S_AGENT),
            "agent",
        ),
        (
            True,
            None,
            "__end__",
        ),
    ],
)
def test_subtask_selector_edge(
    is_last_step: bool, my_task: SubTask | None, expected_output: str
):
    k8s_client = MagicMock()
    k8s_client.mock_add_spec(IK8sClient)

    state = KubernetesAgentState(
        my_task=my_task,
        is_last_step=is_last_step,
        messages=[],
        subtasks=[],
        k8s_client=k8s_client,
    )
    assert subtask_selector_edge(state) == expected_output


@pytest.mark.parametrize(
    "last_message, expected_output",
    [
        (
            ToolMessage(
                content="test",
                tool_call_id="call_MEOW",
                tool_calls={"call_MEOW": "test"},
            ),
            "tools",
        ),
        (
            AIMessage(content="test"),
            "finalizer",
        ),
    ],
)
def test_agent_edge(last_message: BaseMessage, expected_output: str):
    k8s_client = MagicMock()
    k8s_client.mock_add_spec(IK8sClient)

    state = KubernetesAgentState(
        my_task=None,
        is_last_step=False,
        messages=[last_message],
        subtasks=[],
        k8s_client=k8s_client,
    )
    assert agent_edge(state) == expected_output
