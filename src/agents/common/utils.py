from collections.abc import Sequence
from typing import Any, Literal

from gen_ai_hub.proxy.langchain import ChatOpenAI
from langchain.agents import AgentExecutor, OpenAIFunctionsAgent
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.prompts import MessagesPlaceholder
from langgraph.constants import END

from agents.common.constants import (
    CONTINUE,
    ERROR,
    EXIT,
    FINAL_RESPONSE,
    FINALIZER,
    MESSAGES,
    NEXT,
    RECENT_MESSAGES_LIMIT,
    SUBTASKS,
)
from agents.common.state import AgentState, SubTask, SubTaskStatus
from utils.logging import get_logger

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


def agent_node(state: AgentState, agent: AgentExecutor, name: str) -> dict[str, Any]:
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
    last_messages_number: int = RECENT_MESSAGES_LIMIT,
) -> Sequence[BaseMessage]:
    """
    Filter the last n number of messages given last_messages_number.
    Args:
        messages: list of messages
        last_messages_number:  int: number of last messages to return, default is 10

    Returns: list of last messages
    """
    return messages[-last_messages_number:]


def next_step(state: AgentState) -> Literal[EXIT, FINALIZER, CONTINUE]:  # type: ignore
    """Return EXIT if next is EXIT or there is an error, FINALIZER if the next node is FINALIZER, else CONTINUE."""
    if state.next == EXIT:
        logger.debug("Ending the workflow.")
        return EXIT
    if state.error:
        logger.error(f"Exiting the workflow due to the error: {state.error}")
        return EXIT
    return FINALIZER if state.next == FINALIZER else CONTINUE


def exit_node(state: AgentState) -> dict[str, Any]:
    """Used in case of an error."""
    return {
        NEXT: END,
        ERROR: state.error,
        FINAL_RESPONSE: state.final_response,
    }


def create_node_output(
    message: BaseMessage | None = None,
    next: str | None = None,
    subtasks: list[SubTask] | None = None,
    final_response: str | None = None,
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
        FINAL_RESPONSE: final_response,
        ERROR: error,
    }
