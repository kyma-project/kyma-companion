from typing import Any, Sequence

from gen_ai_hub.proxy.langchain import ChatOpenAI
from langchain.agents import AgentExecutor, OpenAIFunctionsAgent
from langchain_core.messages import AIMessage, SystemMessage, BaseMessage
from langchain_core.prompts import MessagesPlaceholder

from agents.common.state import AgentState
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
        if subtask.assigned_to == name:
            try:
                # TODO: move to a specific agent folder and extend it for each agent
                result = agent.invoke({"input": subtask.description})
                subtask.complete()
                return {
                    "messages": [AIMessage(content=result["output"], name=name)],
                }
            except Exception as e:
                logger.error(f"Error in agent {name}: {e}")
                return {
                    "messages": [
                        AIMessage(
                            content=f"Error in agent {name}: {e}",
                            name=name,
                        )
                    ],
                }
    return {"messages": []}


def filter_messages(
    messages: Sequence[BaseMessage], last_messages_number: int = 10
) -> Sequence[BaseMessage]:
    """This is very simple helper function which only ever uses the last four messages"""
    return messages[-last_messages_number:]
