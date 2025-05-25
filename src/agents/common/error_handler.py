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
    async def wrapper(
        self: Any, state: BaseAgentState, config: RunnableConfig
    ) -> dict[str, Any]:

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
    async def wrapper(
        self: Any, state: BaseAgentState, config: RunnableConfig
    ) -> str | None:
        try:
            return await func(self, state, config)
        except Exception:
            logger.exception("Error while summarizing the tool response.")
            return

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
