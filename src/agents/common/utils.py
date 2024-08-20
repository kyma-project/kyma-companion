from typing import Any, Dict

from gen_ai_hub.proxy.langchain import ChatOpenAI
from langchain.agents import AgentExecutor, OpenAIFunctionsAgent
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.prompts import MessagesPlaceholder

from agents.common.state import AgentState


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
        if subtask.assigned_to == name:
            # TODO: add messages next to input for agent invocation
            result = agent.invoke({"input": subtask.description})
            subtask.update_result(result["output"])
            return {
                "messages": [AIMessage(content=result["output"], name=name)],
            }
    return {"messages": []}
