from unittest.mock import Mock

import pytest
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
)

from agents.common.utils import (
    compute_messages_token_count,
    compute_string_token_count,
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
