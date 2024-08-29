from collections.abc import Sequence
from typing import Any, Literal

from gen_ai_hub.proxy.langchain import ChatOpenAI
from langchain.agents import AgentExecutor, OpenAIFunctionsAgent
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.prompts import MessagesPlaceholder
from langgraph.constants import END

from agents.common.state import AgentState
from utils.logging import get_logger

logger = get_logger(__name__)

EXIT = "Exit"


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
                    "messages": [
                        AIMessage(
                            content=f"Error occurred: {e}",
                            name=name,
                        )
                    ],
                }
    return {
        "messages": [
            AIMessage(
                content="All my subtasks are already completed.",
                name=name,
            )
        ]
    }


DEFAULT_NUMBER_OF_MESSAGES = 10


def filter_messages(
    messages: Sequence[BaseMessage],
    last_messages_number: int = DEFAULT_NUMBER_OF_MESSAGES,
) -> Sequence[BaseMessage]:
    """This is very simple helper function which only ever uses the last four messages"""
    return messages[-last_messages_number:]


def should_exit(state: AgentState) -> Literal["exit", "continue"]:
    """Return the next node based on the state."""
    return "exit" if state.error else "continue"


def exit_node(state: AgentState) -> dict[str, Any]:
    """Used in case of an error."""
    logger.error(f"Error in subtasks: {state.error}")
    return {
        "next": END,
    }
