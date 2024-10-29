from typing import Literal

from langchain_core.messages import AIMessage

from agents.kyma.state import KymaAgentState


def subtask_selector_edge(state: KymaAgentState) -> Literal["agent", "__end__"]:
    """Function that determines whether to end or call agent."""
    if state.is_last_step and state.my_task is None:
        return "__end__"
    return "agent"


def agent_edge(state: KymaAgentState) -> Literal["tools", "finalizer"]:
    """Function that determines whether to end or call tools."""
    last_message = state.messages[-1]
    if isinstance(last_message, AIMessage) and not last_message.tool_calls:
        return "finalizer"
    return "tools" 