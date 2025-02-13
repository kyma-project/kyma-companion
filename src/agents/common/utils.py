import hashlib
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, Literal

import tiktoken
from gen_ai_hub.proxy.langchain import ChatOpenAI
from langchain.agents import AgentExecutor, OpenAIFunctionsAgent
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_core.prompts import MessagesPlaceholder
from langgraph.constants import END
from langgraph.graph.message import Messages
from pydantic import BaseModel

from agents.common.constants import (
    CONTINUE,
    ERROR,
    EXIT,
    FINALIZER,
    MESSAGES,
    NEXT,
    RECENT_MESSAGES_LIMIT,
    SUBTASKS,
)
from agents.common.state import CompanionState, SubTask, SubTaskStatus
from utils.logging import get_logger
from utils.models.factory import ModelType

logger = get_logger(__name__)


def create_agent(llm: ChatOpenAI, tools: list, system_prompt: str) -> AgentExecutor:
    """Create an AI agent."""
    agent = OpenAIFunctionsAgent.from_llm_and_tools(
        llm,
        tools,
        extra_prompt_messages=[
            # MessagesPlaceholder(variable_name="messages"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ],
        system_message=SystemMessage(content=system_prompt),
    )
    executor = AgentExecutor(agent=agent, tools=tools)
    return executor


def agent_node(
    state: CompanionState, agent: AgentExecutor, name: str
) -> dict[str, Any]:
    """Agent node."""
    for subtask in state.subtasks:
        if subtask.assigned_to == name and subtask.status != SubTaskStatus.COMPLETED:
            try:
                # TODO: move to a specific agent folder and extend it for each agent
                # TODO: can improved to query all the subtasks at once
                result = agent.invoke(
                    {"messages": state.messages, "input": subtask.description}
                )
                subtask.complete()
                return {
                    MESSAGES: [AIMessage(content=result["output"], name=name)],
                }
            except Exception as e:
                logger.error(f"Error in agent {name}: {e}")
                return {
                    ERROR: str(e),
                    NEXT: EXIT,
                }
    return {
        MESSAGES: [
            AIMessage(
                content="All my subtasks are already completed.",
                name=name,
            )
        ]
    }


def filter_messages(
    messages: Sequence[BaseMessage],
    recent_message_limit: int = RECENT_MESSAGES_LIMIT,
) -> Sequence[BaseMessage]:
    """
    Filter the last n number of messages given last_messages_number.
    Args:
        messages: list of messages
        recent_message_limit:  int: number of last messages to return, default is 10

    Returns: list of last messages
    """
    filtered = messages[-recent_message_limit:]
    # remove the tool messages from head of the list,
    # because a tool message must be preceded by a system message.
    for i, message in enumerate(filtered):
        if not isinstance(message, ToolMessage):
            return filtered[i:]
    return filtered


def next_step(state: CompanionState) -> Literal[EXIT, FINALIZER, CONTINUE]:  # type: ignore
    """Return EXIT if next is EXIT or there is an error, FINALIZER if the next node is FINALIZER, else CONTINUE."""
    if state.next == EXIT:
        logger.debug("Ending the workflow.")
        return EXIT
    if state.error:
        logger.error(f"Exiting the workflow due to the error: {state.error}")
        return EXIT
    return FINALIZER if state.next == FINALIZER else CONTINUE


def create_node_output(
    message: BaseMessage | None = None,
    next: str | None = None,
    subtasks: list[SubTask] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """
    This function is used to create the output of a LangGraph node centrally.

    Args:
        message: BaseMessage | None: message to be sent to the user
        next: str | None: next LangGraph node to be called
        subtasks: list[SubTask] | None: different steps/subtasks to follow
        final_response: str | None: final response to the user
        error: str | None: error message if error occurred
    """
    return {
        MESSAGES: [message] if message else [],
        NEXT: next,
        SUBTASKS: subtasks,
        ERROR: error,
    }


def get_current_day_timestamps_utc() -> tuple[str, str]:
    """
    Returns the start and end timestamps for the current day in UTC.
    Start: 00:00:00
    End: 23:59:59
    """
    # Get the current date in UTC
    now = datetime.now(UTC)

    # Start of the day (00:00:00)
    start_of_day = datetime(now.year, now.month, now.day, 0, 0, 0)

    # End of the day (23:59:59)
    end_of_day = datetime(now.year, now.month, now.day, 23, 59, 59)

    # Format the timestamps in ISO format
    from_timestamp = start_of_day.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    to_timestamp = end_of_day.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    return from_timestamp, to_timestamp


def hash_url(url: str) -> str:
    """
    Generate a 32-character MD5 hash of a given URL.

    :url (str): The URL string to be hashed.

    Returns:
        str: A 32-character hexadecimal string representing the MD5 hash.
    """
    return hashlib.md5(url.encode()).hexdigest()


def compute_string_token_count(text: str, model_type: ModelType) -> int:
    """Returns the token count of the string."""
    return len(tiktoken.encoding_for_model(model_type).encode(text=text))


def compute_messages_token_count(msgs: Messages, model_type: ModelType) -> int:
    """Returns the token count of the messages."""
    tokens_per_msg = (
        compute_string_token_count(str(msg.content), model_type) for msg in msgs
    )
    return sum(tokens_per_msg)


def should_continue(state: BaseModel) -> str:
    """
    Returns END if there is an error, else CONTINUE.
    """
    return END if hasattr(state, ERROR) and state.error else CONTINUE  # type: ignore
