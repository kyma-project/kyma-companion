import functools
import os
from collections.abc import AsyncGenerator
from typing import Any, Literal, Protocol

from gen_ai_hub.proxy.langchain import ChatOpenAI
from langchain.agents import AgentExecutor
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langfuse.callback import CallbackHandler
from langgraph.checkpoint import BaseCheckpointSaver
from langgraph.constants import END
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.graph.graph import CompiledGraph
from pydantic import BaseModel

from utils.agents import create_agent
from utils.logging import get_logger

logger = get_logger(__name__)

langfuse_handler = CallbackHandler(
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    host=os.getenv("LANGFUSE_HOST"),
)


class Message(BaseModel):
    """Message data model."""

    input: str
    session_id: str


class Agent(Protocol):
    """Agent interface."""

    async def astream(self, message: Message) -> dict[str, Any]:
        """Stream the input to the supervisor asynchronously."""
        ...


@tool
def search(query: str) -> list[str]:
    """Call to get information about Kyma."""
    # This is a placeholder for the actual implementation
    return [
        "Kyma is an opinionated set of Kubernetes-based modular building blocks, "
        "including all necessary capabilities to develop and run "
        "enterprise-grade cloud-native applications."
    ]


def should_continue(state: MessagesState) -> Literal["action", "__end__"]:
    """Return the next node to execute."""
    last_message = state["messages"][-1]
    return "action" if last_message.tool_calls else "__end__"


def filter_messages(messages: list) -> list:
    """This is very simple helper function which only ever uses the last four messages"""
    return messages[-10:]


def agent_node(
    state: dict[str, Any], agent: AgentExecutor, name: str
) -> dict[str, Any]:
    """It filters the messages and invokes the agent."""
    state["messages"] = filter_messages(state["messages"])

    result = agent.invoke(state)
    return {"messages": [HumanMessage(content=result["output"], name=name)]}


class SupervisorAgent:
    """Supervisor agent.
    Currently, it has just prelimiary implementation.
    I'll be adding more features to it in the future.
    """

    llm = None
    memory: BaseCheckpointSaver
    kyma_agent = None
    tools = None

    def __init__(self, llm: ChatOpenAI, memory: BaseCheckpointSaver):
        self.llm = llm
        self.memory = memory
        self.tools = [search]
        self.kyma_agent = functools.partial(
            agent_node,
            agent=create_agent(
                llm,
                self.tools,
                "You are Kyma expert. You assist users with Kyma related questions.",
            ),
            name="KymaAgent",
        )
        self.graph = self._build_graph()

    def _build_graph(self) -> CompiledGraph:
        """Create a supervisor agent."""
        kyma_agent_node = self.kyma_agent

        workflow = StateGraph(MessagesState)
        workflow.add_node("agent", kyma_agent_node)  # type: ignore
        workflow.add_edge(START, "agent")
        workflow.add_edge("agent", END)

        graph = workflow.compile(checkpointer=self.memory)
        return graph

    async def astream(self, message: Message) -> AsyncGenerator[dict, None]:
        """Stream the input to the supervisor asynchronously."""
        config = RunnableConfig(
            {
                "configurable": {"thread_id": message.session_id},
                "callbacks": [langfuse_handler],
            }
        )
        async for chunk in self.graph.astream(
            input={"messages": [HumanMessage(content=message.input)]},
            config=config,
        ):
            if "__end__" not in chunk:
                yield chunk
