import operator
from collections.abc import Sequence
from typing import Annotated, Any, TypedDict

from gen_ai_hub.proxy.langchain import ChatOpenAI
from langchain.agents import AgentExecutor, OpenAIFunctionsAgent
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.prompts import MessagesPlaceholder


class AgentState(TypedDict):
    """Agent state."""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    next: str
    subtasks: list[dict[str, str]]
    current_subtask_index: int


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
    current_subtask = state["subtasks"][state["current_subtask_index"]]
    if current_subtask["assigned_to"] == name:
        # TODO: add messages next to input for agent invocation
        result = agent.invoke({"input": current_subtask["description"]})
        return {
            "messages": [AIMessage(content=result["output"], name=name)],
            "current_subtask_index": state["current_subtask_index"] + 1,
        }
    else:
        return {"messages": []}
