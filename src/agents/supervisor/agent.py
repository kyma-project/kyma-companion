import os
from typing import Literal

from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langfuse.callback import CallbackHandler
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.graph import CompiledGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel

from agents.memory.redis_checkpointer import RedisSaver, initialize_async_pool
from utils.logging import get_logger
from utils.models import create_llm

logger = get_logger(__name__)

async_pool = initialize_async_pool(url=f'{os.getenv('REDIS_URL')}/0')
checkpointer = RedisSaver(async_connection=async_pool)

langfuse_handler = CallbackHandler(
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    host=os.getenv("LANGFUSE_HOST"),
)


@tool
def _search(query: str) -> list[str]:
    """Call to surf the web."""
    # This is a placeholder for the actual implementation
    return [
        "It's sunny in Heidelberg, but you better look out if you're a Gemini 😈."
    ]


tools = [_search]
tool_node = ToolNode(tools)
model = create_llm("gpt-4o")
bound_model = model.bind_tools(tools)


def _should_continue(state: MessagesState) -> Literal["action", "__end__"]:
    """Return the next node to execute."""
    last_message = state["messages"][-1]
    # If there is no function call, then we finish
    if not last_message.tool_calls:
        return "__end__"
    return "action"


def _filter_messages(messages: list) -> list:
    """This is very simple helper function which only ever uses the last four messages"""
    return messages[-4:]


def _call_model(state: MessagesState) -> dict:
    """ Call the model with the messages. """
    # messages = _filter_messages(state["messages"])
    response = model.invoke(state["messages"])
    # We return a list, because this will get added to the existing list
    return {"messages": response}


def _create_supervisor() -> CompiledGraph:
    """ Create a supervisor agent. """

    workflow = StateGraph(MessagesState)

    workflow.add_node("agent", _call_model)
    workflow.add_node("action", tool_node)

    workflow.add_edge(START, "agent")

    # We now add a conditional edge
    workflow.add_conditional_edges(
        "agent",
        _should_continue,
    )

    workflow.add_edge("action", "agent")

    graph = workflow.compile(checkpointer=checkpointer)
    return graph


supervisor_graph = _create_supervisor()


class Message(BaseModel):
    """ Message model """
    input: str
    session_id: str


async def astream(message: Message):  # noqa: ANN201
    """ Stream the input to the supervisor asynchronously. """
    config = {
        "configurable": {"thread_id": message.session_id},
        "callbacks": [langfuse_handler]
    }
    async for chunk in supervisor_graph.astream(
            input={
                "messages": [
                    HumanMessage(content=message.input)
                ]
            },
            config=config,
    ):
        if "__end__" not in chunk:
            yield chunk


def stream(message: Message):  # noqa: ANN201
    """ Stream the input to the supervisor synchronously. """
    config = {
        "configurable": {"thread_id": message.session_id},
        "callbacks": [langfuse_handler]
    }
    for chunk in supervisor_graph.stream(
            input={
                "messages": [
                    HumanMessage(content=message.input)
                ]
            },
            config=config,
    ):
        if "__end__" not in chunk:
            yield chunk
