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

from agents.common.agent import AGENT_STEPS_NUMBER, agent_edge, subtask_selector_edge
from agents.common.state import CompanionState, SubTask, SubTaskStatus
from agents.common.utils import (
    RECENT_MESSAGES_LIMIT,
    compute_messages_token_count,
    compute_string_token_count,
    filter_k8s_data,
    filter_kyma_data,
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
        remaining_steps=25,
    )
    assert subtask_selector_edge(state) == expected_output


@pytest.mark.parametrize(
    "last_message, remaining_steps, has_task, expected_output",
    [
        # Case 1: Tool message with sufficient remaining steps -> tools
        (
            ToolMessage(
                content="test",
                tool_call_id="call_MEOW",
                tool_calls={"call_MEOW": "test"},
            ),
            9,
            False,
            "tools",
        ),
        # Case 2: AI message without tool calls -> finalizer
        (
            AIMessage(content="test"),
            9,
            False,
            "finalizer",
        ),
        # Case 3: AI message with tool calls -> tools
        (
            AIMessage(
                content="test",
                tool_calls=[{"name": "some_tool", "id": "call_123", "args": {}}],
            ),
            9,
            False,
            "tools",
        ),
        # Case 4: Insufficient remaining steps without task -> finalizer
        (
            AIMessage(content="test"),
            0,
            False,
            "finalizer",
        ),
        # Case 5: Insufficient remaining steps with task -> finalizer (and task status updated)
        (
            AIMessage(content="test"),
            0,
            True,
            "finalizer",
        ),
        # Case 6: Empty message list edge case
        (
            AIMessage(content=""),
            9,
            False,
            "finalizer",
        ),
        # Case 7: AI message with empty tool_calls list
        (
            AIMessage(content="test", tool_calls=[]),
            9,
            False,
            "finalizer",
        ),
        # Case 8: Tool message with insufficient remaining steps -> finalizer
        (
            ToolMessage(
                content="test",
                tool_call_id="call_MEOW",
                tool_calls={"call_MEOW": "test"},
            ),
            0,
            False,
            "finalizer",
        ),
    ],
)
def test_agent_edge(
    last_message: BaseMessage,
    remaining_steps: int,
    has_task: bool,
    expected_output: str,
):
    k8s_client = MagicMock()
    k8s_client.mock_add_spec(IK8sClient)

    # Create a task if needed for the test case
    my_task = None
    if has_task:
        my_task = MagicMock(spec=SubTask)
        my_task.status = SubTaskStatus.PENDING

    state = KubernetesAgentState(
        my_task=my_task,
        is_last_step=False,
        messages=[],
        agent_messages=[last_message],
        subtasks=[],
        k8s_client=k8s_client,
        remaining_steps=remaining_steps,
    )

    result = agent_edge(state)
    assert result == expected_output

    # Verify task status is updated when remaining steps is insufficient
    if has_task and remaining_steps <= AGENT_STEPS_NUMBER:
        assert my_task.status == SubTaskStatus.ERROR


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


@pytest.mark.parametrize(
    "input_data, expected_output",
    [
        # Pod in Running phase should return None
        (
            {
                "metadata": {"name": "pod1", "managedFields": [{"key": "value"}]},
                "status": {"phase": "Running"},
            },
            None,
        ),
        # Pod not in Running phase should return data without managedFields
        (
            {
                "metadata": {"name": "pod2", "managedFields": [{"key": "value"}]},
                "status": {"phase": "Pending"},
            },
            {"metadata": {"name": "pod2"}, "status": {"phase": "Pending"}},
        ),
        # Pod with no phase should return data without managedFields
        (
            {
                "metadata": {"name": "pod3", "managedFields": [{"key": "value"}]},
                "status": {},
            },
            {"metadata": {"name": "pod3"}, "status": {}},
        ),
        # Pod with no status should return data without managedFields
        (
            {"metadata": {"name": "pod4", "managedFields": [{"key": "value"}]}},
            {"metadata": {"name": "pod4"}},
        ),
        # Pod with no managedFields should work normally
        (
            {"metadata": {"name": "pod5"}, "status": {"phase": "Failed"}},
            {"metadata": {"name": "pod5"}, "status": {"phase": "Failed"}},
        ),
        # Case-insensitive check for Running phase
        (
            {"metadata": {"name": "pod6"}, "status": {"phase": "running"}},  # lowercase
            None,
        ),
        # Empty input should return empty output
        ({}, {}),
    ],
)
def test_filter_k8s_data(input_data, expected_output):

    result = filter_k8s_data(input_data)

    if expected_output is None:
        assert result is None
    else:
        assert result == expected_output
        # Verify managedFields is always removed when metadata exists
        if "metadata" in input_data and "managedFields" in input_data["metadata"]:
            assert "managedFields" not in result["metadata"]


@pytest.mark.parametrize(
    "input_data, expected_output",
    [
        # APIRuleStatus is 'OK' (case-insensitive) should return None
        (
            {
                "metadata": {"name": "kyma1", "managedFields": [{"key": "value"}]},
                "status": {"APIRuleStatus": {"code": "OK"}},
            },
            None,
        ),
        # APIRuleStatus is not 'OK' should return data without managedFields
        (
            {
                "metadata": {"name": "kyma2", "managedFields": [{"key": "value"}]},
                "status": {"APIRuleStatus": {"code": "Error"}},
            },
            {
                "metadata": {"name": "kyma2"},
                "status": {"APIRuleStatus": {"code": "Error"}},
            },
        ),
        # No APIRuleStatus code should return data without managedFields
        (
            {
                "metadata": {"name": "kyma3", "managedFields": [{"key": "value"}]},
                "status": {"APIRuleStatus": {}},
            },
            {"metadata": {"name": "kyma3"}, "status": {"APIRuleStatus": {}}},
        ),
        # No APIRuleStatus should return data without managedFields
        (
            {
                "metadata": {"name": "kyma4", "managedFields": [{"key": "value"}]},
                "status": {},
            },
            {"metadata": {"name": "kyma4"}, "status": {}},
        ),
        # No status should return data without managedFields
        (
            {"metadata": {"name": "kyma5", "managedFields": [{"key": "value"}]}},
            {"metadata": {"name": "kyma5"}},
        ),
        # No managedFields should work normally
        (
            {
                "metadata": {"name": "kyma6"},
                "status": {"APIRuleStatus": {"code": "Error"}},
            },
            {
                "metadata": {"name": "kyma6"},
                "status": {"APIRuleStatus": {"code": "Error"}},
            },
        ),
        # Different case for 'OK' should still return None
        (
            {
                "metadata": {"name": "kyma7"},
                "status": {"APIRuleStatus": {"code": "ok"}},  # lowercase
            },
            None,
        ),
        # Empty input should return empty output
        ({}, {}),
    ],
)
def test_filter_kyma_data(input_data, expected_output):

    result = filter_kyma_data(input_data)

    if expected_output is None:
        assert result is None
    else:
        assert result == expected_output
        # Verify managedFields is always removed when metadata exists
        if "metadata" in input_data and "managedFields" in input_data["metadata"]:
            assert "managedFields" not in result.get("metadata", {})
