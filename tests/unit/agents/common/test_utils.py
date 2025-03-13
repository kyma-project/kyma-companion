from collections.abc import Sequence
from unittest.mock import MagicMock, Mock

import pytest
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from agents.common.agent import agent_edge, subtask_selector_edge
from agents.common.state import CompanionState, SubTask
from agents.common.utils import (
    RECENT_MESSAGES_LIMIT,
    compute_messages_token_count,
    compute_string_token_count,
    filter_messages,
)
from agents.k8s.agent import K8S_AGENT
from agents.k8s.state import KubernetesAgentState
from services.k8s import IK8sClient
from utils.models.factory import ModelType

# Mock the logging setup
mock_logger = Mock()
mock_get_logger = Mock(return_value=Mock())


@pytest.fixture
def mock_llm():
    return Mock()


@pytest.fixture
def mock_tools():
    return [Mock(), Mock()]


@pytest.fixture
def mock_agent_executor():
    return Mock()


@pytest.fixture
def mock_state():
    return Mock(spec=CompanionState, messages=[HumanMessage(content="Hello Test")])


@pytest.mark.parametrize(
    "messages, last_messages_number, expected_output",
    [
        # Test case 1: Less messages than the limit
        (
            [HumanMessage(content="Hello"), AIMessage(content="Hi there")],
            10,
            [HumanMessage(content="Hello"), AIMessage(content="Hi there")],
        ),
        # Test case 2: Exactly the number of messages as the limit
        (
            [
                HumanMessage(content="A"),
                AIMessage(content="B"),
                HumanMessage(content="C"),
            ],
            3,
            [
                HumanMessage(content="A"),
                AIMessage(content="B"),
                HumanMessage(content="C"),
            ],
        ),
        # Test case 3: More messages than the limit
        (
            [
                SystemMessage(content="System"),
                HumanMessage(content="1"),
                AIMessage(content="2"),
                HumanMessage(content="3"),
                AIMessage(content="4"),
            ],
            2,
            [HumanMessage(content="3"), AIMessage(content="4")],
        ),
        # Test case 4: Empty input
        ([], 5, []),
        # Test case 5: Custom last_messages_number
        (
            [
                HumanMessage(content="A"),
                AIMessage(content="B"),
                HumanMessage(content="C"),
                AIMessage(content="D"),
                HumanMessage(content="E"),
            ],
            4,
            [
                AIMessage(content="B"),
                HumanMessage(content="C"),
                AIMessage(content="D"),
                HumanMessage(content="E"),
            ],
        ),
        # Test case 6: last_messages_number = 1
        (
            [
                HumanMessage(content="First"),
                AIMessage(content="Second"),
                HumanMessage(content="Third"),
            ],
            1,
            [HumanMessage(content="Third")],
        ),
        # Test case 7: Tool messages on head of result list.
        (
            [
                AIMessage(content="Second"),
                ToolMessage(content="Tool message 1", tool_call_id="call_MEOW"),
                ToolMessage("Tool message 2", tool_call_id="call_WOF"),
                HumanMessage(content="First"),
                AIMessage(content="Second"),
                HumanMessage(content="Third"),
            ],
            5,
            [
                HumanMessage(content="First"),
                AIMessage(content="Second"),
                HumanMessage(content="Third"),
            ],
        ),
    ],
)
def test_filter_messages(
    messages: Sequence[BaseMessage],
    last_messages_number: int,
    expected_output: Sequence[BaseMessage],
):
    result = filter_messages(messages, last_messages_number)

    assert len(result) == len(expected_output)
    for res_msg, exp_msg in zip(result, expected_output, strict=False):
        assert type(res_msg) is type(exp_msg)
        assert res_msg.content == exp_msg.content


def test_filter_messages_default_parameter():
    messages = [HumanMessage(content=str(i)) for i in range(15)]
    result = filter_messages(messages)  # Using default last_messages_number
    assert len(result) == RECENT_MESSAGES_LIMIT
    assert [msg.content for msg in result] == [str(i) for i in range(5, 15)]


@pytest.mark.parametrize(
    "is_last_step, my_task, expected_output",
    [
        (
            False,
            SubTask(description="test", task_title="test", assigned_to=K8S_AGENT),
            "agent",
        ),
        (
            True,
            None,
            "finalizer",
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
        agent_messages=[],
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
        messages=[],
        agent_messages=[last_message],
        subtasks=[],
        k8s_client=k8s_client,
    )
    assert agent_edge(state) == expected_output


@pytest.mark.parametrize(
    "text, model_type, expected_token_count",
    [
        ("Hello, world!", ModelType.GPT4O, 4),
        ("This is a test.", ModelType.GPT4O, 5),  # Example token count
        ("", ModelType.GPT4O, 0),  # Empty string
        (
            "A longer text input to test the token count.",
            ModelType.GPT4O,
            10,
        ),  # Example token count
    ],
)
def test_compute_string_token_count(text, model_type, expected_token_count):
    assert compute_string_token_count(text, model_type) == expected_token_count


@pytest.mark.parametrize(
    "msgs, model_type, expected_token_count",
    [
        (
            [HumanMessage(content="Hello"), AIMessage(content="Hi there")],
            ModelType.GPT4O,
            3,  # Example token count
        ),
        (
            [
                HumanMessage(content="This is a test."),
                AIMessage(content="Another test."),
            ],
            ModelType.GPT4O,
            8,  # Example token count
        ),
        ([], ModelType.GPT4O, 0),  # No messages
        (
            [HumanMessage(content="A longer text input to test the token count.")],
            ModelType.GPT4O,
            10,  # Example token count
        ),
    ],
)
def test_compute_messages_token_count(msgs, model_type, expected_token_count):
    assert compute_messages_token_count(msgs, model_type) == expected_token_count
