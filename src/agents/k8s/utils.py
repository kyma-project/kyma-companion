from typing import Literal

from langchain_core.messages import AIMessage

from agents.k8s.agent import KubernetesAgentState


def subtask_selector_edge(state: KubernetesAgentState) -> Literal["agent", "__end__"]:
    """Function that determines whether to end or call agent."""
    if state.is_last_step and state.my_task is None:
        return "__end__"
    return "agent"


def agent_edge(state: KubernetesAgentState) -> Literal["tools", "__end__"]:
    """Function that determines whether to end or call tools."""
    last_message = state.messages[-1]
    if isinstance(last_message, AIMessage) and not last_message.tool_calls:
        return "__end__"
    return "tools"
