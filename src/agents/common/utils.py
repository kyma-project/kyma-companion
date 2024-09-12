from collections.abc import Sequence
from typing import Any, Literal

from gen_ai_hub.proxy.langchain import ChatOpenAI
from langchain.agents import AgentExecutor, OpenAIFunctionsAgent
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.prompts import MessagesPlaceholder
from langgraph.constants import END

from agents.common.constants import CONTINUE, EXIT, FILTER_MESSAGES_NUMBER, FINALIZER
from agents.common.state import AgentState, SubTask
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
        if subtask.assigned_to == name and subtask.status != "completed":
            try:
                # TODO: move to a specific agent folder and extend it for each agent
                # TODO: can improved to query all the subtasks at once
                result = agent.invoke(
                    {"messages": state.messages, "input": subtask.description}
                )
                subtask.complete()
                return {
                    "messages": [AIMessage(content=result["output"], name=name)],
                }
            except Exception as e:
                logger.error(f"Error in agent {name}: {e}")
                return {
                    "error": str(e),
                    "next": EXIT,
                }
    return {
        "messages": [
            AIMessage(
                content="All my subtasks are already completed.",
                name=name,
            )
        ]
    }


def filter_messages(
    messages: Sequence[BaseMessage],
    last_messages_number: int = FILTER_MESSAGES_NUMBER,
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
    """Return EXIT if there is an error, FINALIZER if the next node is FINALIZER, else CONTINUE."""
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
        "next": END,
        "error": state.error,
        "final_response": state.final_response,
    }


def create_node_output(
    message: BaseMessage | None = None,
    next: str | None = None,
    subtasks: list[SubTask] | None = None,
    final_response: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Create a LangGraph node output."""
    return {
        "messages": [message] if message else [],
        "next": next,
        "subtasks": subtasks,
        "final_response": final_response,
        "error": error,
    }
