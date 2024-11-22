from collections.abc import Callable, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from agents.common.constants import FINALIZER


def filter_messages_via_checks(
    messages: Sequence[BaseMessage], checks: list[Callable[[BaseMessage], bool]]
) -> Sequence[BaseMessage]:
    """
    Filter messages by checking if a messages passes any of the checks.


    Args:
        messages (Sequence[BaseMessage]): Sequence of messages to filter.
        checks (list[Callable[[BaseMessage], bool]]): List of checks to apply to the messages.
            A massages passes if it matches ANY of the checks, not ALL.

    Returns:
        Sequence[BaseMessage]: Filtered messages, that passed any of the checks.
    """
    return [message for message in messages if any(check(message) for check in checks)]


def filter_most_recent_messages(
    messages: Sequence[BaseMessage], number_of_messages: int
) -> Sequence[BaseMessage]:
    """
    Filter messages, to return only a defined number of the most recent messages.

    Args:
        messages (Sequence[BaseMessage]): Sequence of messages to filter.
        number_of_messages (int): Number of most recent messages to return.

    Returns:
        Sequence[BaseMessage]: Filtered messages, that are the most recent messages.
    """
    return messages[-number_of_messages:]


def is_human_message(message: BaseMessage) -> bool:
    """Check if a message is a human message. Can be used as a check in the 'filter_messages_via_checks' function."""
    return isinstance(message, HumanMessage)


def is_finalizer_message(message: BaseMessage) -> bool:
    """
    Check if a message is a finalizer message. Can be used as a check in the
    'filter_messages_via_checks' function.
    """
    return isinstance(message, AIMessage) and message.name == FINALIZER


def is_system_message(message: BaseMessage) -> bool:
    """Check if a message is a system message. Can be used as a check in the 'filter_messages_via_checks' function."""
    return isinstance(message, SystemMessage)
