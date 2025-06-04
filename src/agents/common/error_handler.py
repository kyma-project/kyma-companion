import functools
from collections.abc import Callable
from typing import Any

from utils.logging import get_logger

logger = get_logger(__name__)


def tool_parsing_error_handler(func: Callable) -> Callable:
    """
    Decorator to handle tool message parsing errors gracefully.

    This decorator catches parsing exceptions and logs warnings while allowing
    the process to continue with other messages.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Failed to parse tool message content: {e}")
            return None  # Return None to indicate parsing failed

    return wrapper


def token_counting_error_handler(func: Callable) -> Callable:
    """
    Decorator to handle token counting errors gracefully.

    This decorator catches token counting exceptions and returns an empty string
    to indicate that summarization should be skipped.
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Failed to compute token count: {e}")
            return 0  # Return 0 to indicate token counting failed

    return wrapper
