import functools
from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables.config import RunnableConfig

from agents.common.constants import AGENT_MESSAGES, ERROR
from agents.common.state import BaseAgentState, SubTaskStatus
from utils.logging import get_logger

logger = get_logger(__name__)

# as default recursive limit is 25 and the graph has 3 nodes
# the latest call must withing the nodes (steps) number
AGENT_STEPS_NUMBER = 3


def agent_error_handler(func: Callable) -> Callable:
    """
    Decorator to handle errors in agent methods.

    This decorator catches exceptions and returns appropriate error responses
    for agent methods that return dict[str, Any] with AGENT_MESSAGES.
    """

    @functools.wraps(func)
    async def wrapper(self: Any, state: BaseAgentState, config: RunnableConfig) -> Any:

        try:
            return await func(self, state, config)
        except Exception as e:
            error_message = "An error occurred while processing the request"
            error_message_with_trace = error_message + f": {e}"
            logger.error(error_message_with_trace)

            # Update current subtask status
            if state.my_task:
                state.my_task.status = SubTaskStatus.ERROR

            return {
                AGENT_MESSAGES: [
                    AIMessage(
                        content="Sorry, an unexpected error occurred while processing your request. "
                        "Please try again later.",
                        name=self.name,
                    )
                ],
                ERROR: error_message,  # we dont send trace to frontend
            }

    return wrapper


def tool_summarization_error_handler(func: Callable) -> Callable:
    """
    Decorator to handle errors specifically in tool summarization methods.

    This decorator catches exceptions during tool response summarization
    and returns an empty string to indicate summarization failed.
    """

    @functools.wraps(func)
    async def wrapper(self: Any, state: BaseAgentState, config: RunnableConfig) -> Any:
        try:
            return await func(self, state, config)
        except Exception:
            logger.exception("Error while summarizing the tool response.")
            return

    return wrapper


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


def summarization_execution_error_handler(func: Callable) -> Callable:
    """
    Decorator to handle summarization execution errors.

    This decorator catches exceptions during the actual summarization process
    and re-raises them with additional logging context.
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            result = await func(*args, **kwargs)
            logger.info("Tool Response Summarization completed successfully")
            return result
        except Exception as e:
            logger.error(f"Tool response summarization failed: {e}")
            raise

    return wrapper


def _handle_recursive_limit_error(
    agent_name: str, state: BaseAgentState
) -> dict[str, Any]:
    """Handle recursive limit error."""
    if state.my_task:
        state.my_task.status = SubTaskStatus.ERROR

    logger.error(
        f"Agent reached the recursive limit, steps remaining: {state.remaining_steps}."
    )
    return {
        AGENT_MESSAGES: [
            AIMessage(
                content="Agent reached the recursive limit, not able to call Tools again",
                name=agent_name,
            )
        ],
    }
