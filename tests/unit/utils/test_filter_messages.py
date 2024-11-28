import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from agents.common.constants import FINALIZER
from utils.filter_messages import (
    filter_messages_via_checks,
    filter_most_recent_messages,
    is_finalizer_message,
    is_human_message,
    is_system_message,
)


@pytest.mark.parametrize(
    "test_case,messages,checks,expected_result",
    [
        (
            "should return no messages when no checks are applied",
            [
                HumanMessage(content="Human Message"),
                AIMessage(content="AI Message"),
                SystemMessage(content="Sysytem Message"),
            ],
            [],  # no checks
            [],
        ),
        (
            "should return only human messages",
            [
                HumanMessage(content="Human Message"),
                AIMessage(content="AI Message"),
                SystemMessage(content="Sysytem Message"),
            ],
            [is_human_message],
            [
                HumanMessage(content="Human Message"),
            ],
        ),
        (
            "should return only finalizer messages",
            [
                HumanMessage(content="Human Message"),
                AIMessage(content="AI Message"),
                # Finalizer messages are AIMessages with the name "FINALIZER":
                AIMessage(content="Finalizer Message", name=FINALIZER),
                SystemMessage(content="Sysytem Message"),
            ],
            [is_finalizer_message],
            [
                AIMessage(content="Finalizer Message", name=FINALIZER),
            ],
        ),
        (
            "should return only system messages",
            [
                HumanMessage(content="Human Message"),
                AIMessage(content="AI Message"),
                SystemMessage(content="Sysytem Message"),
            ],
            [is_system_message],
            [
                SystemMessage(content="Sysytem Message"),
            ],
        ),
        (
            "should handle two checks",
            [
                HumanMessage(content="Human Message"),
                AIMessage(content="AI Message"),
                AIMessage(content="Finalizer Message", name=FINALIZER),
                SystemMessage(content="Sysytem Message"),
            ],
            [is_human_message, is_finalizer_message],
            [
                HumanMessage(content="Human Message"),
                AIMessage(content="Finalizer Message", name=FINALIZER),
            ],
        ),
        (
            "should handle three checks",
            [
                HumanMessage(content="Human Message"),
                AIMessage(content="AI Message"),
                AIMessage(content="Finalizer Message", name=FINALIZER),
                SystemMessage(content="Sysytem Message"),
            ],
            [is_human_message, is_finalizer_message, is_system_message],
            [
                HumanMessage(content="Human Message"),
                AIMessage(content="Finalizer Message", name=FINALIZER),
                SystemMessage(content="Sysytem Message"),
            ],
        ),
        (
            "should return empty list when no messages pass the checks",
            [
                HumanMessage(content="Human Message"),
                AIMessage(content="AI Message"),
                SystemMessage(content="Sysytem Message"),
            ],
            [is_finalizer_message],
            [],
        ),
    ],
)
def test_filter_messages_via_checks(test_case, messages, checks, expected_result):
    """
    The purpose of this test is to test the filter_messages_via_checks function
    by passing in a sequence of messages and a list of checks and checking
    if the function returns the expected, filtered sequence of messages.
    """
    result = filter_messages_via_checks(messages, checks)
    assert result == expected_result


@pytest.mark.parametrize(
    "test_case,messages,number_of_messages,expected_result",
    [
        (
            "should return the most recent message",
            [
                HumanMessage(content="Human Message 1"),
                AIMessage(content="AI Message 1"),
                SystemMessage(content="Sysytem Message 1"),
                HumanMessage(content="Human Message 2"),
                AIMessage(content="AI Message 2"),
                SystemMessage(content="Sysytem Message 2"),
            ],
            1,
            [
                SystemMessage(content="Sysytem Message 2"),
            ],
        ),
        (
            "should return the 2 most recent messages",
            [
                HumanMessage(content="Human Message 1"),
                AIMessage(content="AI Message 1"),
                SystemMessage(content="Sysytem Message 1"),
                HumanMessage(content="Human Message 2"),
                AIMessage(content="AI Message 2"),
                SystemMessage(content="Sysytem Message 2"),
            ],
            2,
            [
                AIMessage(content="AI Message 2"),
                SystemMessage(content="Sysytem Message 2"),
            ],
        ),
        (
            "should return the 3 most recent messages",
            [
                HumanMessage(content="Human Message 1"),
                AIMessage(content="AI Message 1"),
                SystemMessage(content="Sysytem Message 1"),
                HumanMessage(content="Human Message 2"),
                AIMessage(content="AI Message 2"),
                SystemMessage(content="Sysytem Message 2"),
            ],
            3,
            [
                HumanMessage(content="Human Message 2"),
                AIMessage(content="AI Message 2"),
                SystemMessage(content="Sysytem Message 2"),
            ],
        ),
    ],
)
def test_filter_most_recent_messages(
    test_case, messages, number_of_messages, expected_result
):
    """
    The purpose of this test is to test the filter_most_recent_messages function
    by passing in a sequence of messages and a number of messages to return
    and verifying if the function returns the expected, filtered sequence of messages.
    """
    result = filter_most_recent_messages(messages, number_of_messages)
    assert result == expected_result
