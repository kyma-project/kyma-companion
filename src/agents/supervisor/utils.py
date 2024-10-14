from typing import Literal

from langchain_core.messages import AIMessage

from agents.common.state import AgentState


def planner_edge(state: AgentState) -> Literal["Supervisor", "__end__"]:
    """Function that determines whether to end or call Supervisor."""
    last_message = state.messages[-1]
    if isinstance(last_message, AIMessage) and not last_message.tool_calls:
        return "__end__"
    return "Supervisor"