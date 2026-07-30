from collections.abc import Sequence
from unittest.mock import Mock

import pytest
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from agents.common.utils import (
    RECENT_MESSAGES_LIMIT,
    compute_messages_token_count,
    compute_string_token_count,
    filter_messages,
    filter_valid_messages,
)

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
    "text, model_type, expected_token_count",
    [
        ("Hello, world!", "gpt-4o", 4),
        ("This is a test.", "gpt-4o", 5),  # Example token count
        ("", "gpt-4o", 0),  # Empty string
        (
            "A longer text input to test the token count.",
            "gpt-4o",
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
            "gpt-4o",
            3,  # Example token count
        ),
        (
            [
                HumanMessage(content="This is a test."),
                AIMessage(content="Another test."),
            ],
            "gpt-4o",
            8,  # Example token count
        ),
        ([], "gpt-4o", 0),  # No messages
        (
            [HumanMessage(content="A longer text input to test the token count.")],
            "gpt-4o",
            10,  # Example token count
        ),
    ],
)
def test_compute_messages_token_count(msgs, model_type, expected_token_count):
    assert compute_messages_token_count(msgs, model_type) == expected_token_count


@pytest.mark.parametrize(
    "test_description, input_messages, expected_output",
    [
        (
            "Valid sequence with AIMessage and ToolMessages",
            [
                AIMessage(
                    content="AI message",
                    tool_calls=[
                        {
                            "type": "call_1",
                            "name": "call_1",
                            "id": "call_1",
                            "args": {"a": 1},
                        },
                        {
                            "type": "call_2",
                            "name": "call_2",
                            "id": "call_2",
                            "args": {"a": 1},
                        },
                    ],
                ),
                ToolMessage(content="Tool message 1", tool_call_id="call_1"),
                ToolMessage(content="Tool message 2", tool_call_id="call_2"),
            ],
            [
                AIMessage(
                    content="AI message",
                    tool_calls=[
                        {
                            "type": "call_1",
                            "name": "call_1",
                            "id": "call_1",
                            "args": {"a": 1},
                        },
                        {
                            "type": "call_2",
                            "name": "call_2",
                            "id": "call_2",
                            "args": {"a": 1},
                        },
                    ],
                ),
                ToolMessage(content="Tool message 1", tool_call_id="call_1"),
                ToolMessage(content="Tool message 2", tool_call_id="call_2"),
            ],
        ),
        (
            "Invalid sequence with AIMessage missing one ToolMessage out of two.",
            [
                HumanMessage(content="Human message"),
                AIMessage(
                    content="AI message",
                    tool_calls=[
                        {
                            "type": "call_1",
                            "name": "call_1",
                            "id": "call_1",
                            "args": {"a": 1},
                        },
                        {
                            "type": "call_2",
                            "name": "call_2",
                            "id": "call_2",
                            "args": {"a": 1},
                        },
                    ],
                ),
                ToolMessage(content="Tool message 1", tool_call_id="call_1"),
            ],
            [
                HumanMessage(content="Human message"),
            ],
        ),
        (
            "Invalid sequence with AIMessage missing ToolMessages",
            [
                AIMessage(
                    content="AI message",
                    tool_calls=[
                        {
                            "type": "call_1",
                            "name": "call_1",
                            "id": "call_1",
                            "args": {"a": 1},
                        },
                    ],
                ),
                HumanMessage(content="Human message"),
            ],
            [
                HumanMessage(content="Human message"),
            ],
        ),
        (
            "ToolMessage without preceding AIMessage",
            [
                ToolMessage(content="Tool message", tool_call_id="call_1"),
                HumanMessage(content="Human message"),
                ToolMessage(content="Tool message", tool_call_id="call_2"),
            ],
            [
                HumanMessage(content="Human message"),
            ],
        ),
        (
            "AIMessage without tool_calls",
            [
                AIMessage(content="AI message 1"),
                HumanMessage(content="Human message"),
                AIMessage(content="AI message 2"),
                ToolMessage(content="Tool message", tool_call_id="call_2"),
            ],
            [
                AIMessage(content="AI message 1"),
                HumanMessage(content="Human message"),
                AIMessage(content="AI message 2"),
            ],
        ),
        (
            "Mixed valid and invalid sequences",
            [
                AIMessage(
                    content="AI message",
                    tool_calls=[
                        {
                            "type": "call_1",
                            "name": "call_1",
                            "id": "call_1",
                            "args": {"a": 1},
                        },
                    ],
                ),
                ToolMessage(content="Tool message 1", tool_call_id="call_1"),
                HumanMessage(content="Human message"),
                ToolMessage(content="Tool message 2", tool_call_id="call_2"),
                AIMessage(
                    content="AI message",
                    tool_calls=[
                        {
                            "type": "call_2",
                            "name": "call_2",
                            "id": "call_2",
                            "args": {"a": 1},
                        },
                    ],
                ),
            ],
            [
                AIMessage(
                    content="AI message",
                    tool_calls=[
                        {
                            "type": "call_1",
                            "name": "call_1",
                            "id": "call_1",
                            "args": {"a": 1},
                        },
                    ],
                ),
                ToolMessage(content="Tool message 1", tool_call_id="call_1"),
                HumanMessage(content="Human message"),
            ],
        ),
        (
            "Empty input",
            [],
            [],
        ),
        (
            "Should not raise an error when next_messages index is out of range",
            [
                HumanMessage(content="Human message"),
                AIMessage(
                    content="AI message",
                    tool_calls=[
                        {
                            "type": "call_1",
                            "name": "call_1",
                            "id": "call_1",
                            "args": {"a": 1},
                        },
                        {
                            "type": "call_2",
                            "name": "call_2",
                            "id": "call_2",
                            "args": {"a": 1},
                        },
                        {
                            "type": "call_3",
                            "name": "call_3",
                            "id": "call_3",
                            "args": {"a": 1},
                        },
                    ],
                ),
                ToolMessage(content="Tool message 1", tool_call_id="call_1"),
            ],
            [
                HumanMessage(content="Human message"),
            ],
        ),
    ],
)
def test_filter_valid_messages(test_description, input_messages, expected_output):
    result = filter_valid_messages(input_messages)
    assert result == expected_output, test_description
