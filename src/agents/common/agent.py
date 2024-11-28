from typing import Any, Literal, Protocol

from langchain_core.embeddings import Embeddings
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    RemoveMessage,
    ToolMessage,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from agents.common.constants import IS_LAST_STEP, MESSAGES, MY_TASK, OWNER
from agents.common.state import BaseAgentState, SubTaskStatus
from agents.common.utils import filter_messages
from utils.models.factory import IModel


def subtask_selector_edge(state: BaseAgentState) -> Literal["agent", "__end__"]:
    """Function that determines whether to end or call agent."""
    if state.is_last_step and state.my_task is None:
        return "__end__"
    return "agent"


def agent_edge(state: BaseAgentState) -> Literal["tools", "finalizer"]:
    """Function that determines whether to call tools or finalizer."""
    last_message = state.messages[-1]
    if isinstance(last_message, AIMessage) and not last_message.tool_calls:
        return "finalizer"
    return "tools"


class IAgent(Protocol):
    """Agent interface."""

    def agent_node(self):  # noqa ANN
        """Main agent function."""
        ...

    @property
    def name(self) -> str:
        """Agent name."""
        ...


class BaseAgent:
    """Abstract base agent class."""

    def __init__(
        self,
        name: str,
        model: IModel | Embeddings,
        tools: list,
        system_prompt: str,
        state_class: type,
    ):
        self._name = name
        self.model = model
        self.tools = tools
        self.chain = self._create_chain(system_prompt)
        self.graph = self._build_graph(state_class)
        self.graph.step_timeout = 60  # Default timeout, can be overridden

    @property
    def name(self) -> str:
        """Agent name."""
        return self._name

    def agent_node(self) -> Any:
        """Get agent node function."""
        return self.graph

    def is_internal_message(self, message: BaseMessage) -> bool:
        """Check if the message is an internal message."""
        # if the message is a tool call and the owner is the agent, return True.
        if (
            message.additional_kwargs is not None
            and OWNER in message.additional_kwargs
            and message.additional_kwargs[OWNER] == self.name
            and message.tool_calls  # type: ignore
        ):
            return True

        # if the message is a tool message and the tool is in the agent's tools, return True.
        tool_names = [tool.name for tool in self.tools]
        if isinstance(message, ToolMessage) and message.name in tool_names:
            return True
        return False

    def _create_chain(self, system_prompt: str) -> Any:
        agent_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder(variable_name=MESSAGES),
                ("human", "{query}"),
            ]
        )
        return agent_prompt | self.model.llm.bind_tools(self.tools)

    def _subtask_selector_node(self, state: BaseAgentState) -> dict[str, Any]:
        if state.k8s_client is None:
            raise ValueError("Kubernetes client is not initialized.")

        # find subtasks assigned to this agent and not completed.
        for subtask in state.subtasks:
            if (
                subtask.assigned_to == self.name
                and subtask.status != SubTaskStatus.COMPLETED
            ):
                return {
                    MY_TASK: subtask,
                }

        return {
            IS_LAST_STEP: True,
            MESSAGES: [
                AIMessage(
                    content="All my subtasks are already completed.",
                    name=self.name,
                )
            ],
        }

    def _invoke_chain(self, state: BaseAgentState, config: RunnableConfig) -> Any:
        inputs = {
            MESSAGES: filter_messages(state.messages),
            "query": state.my_task.description,
        }
        response = self.chain.invoke(inputs, config)
        return response

    def _model_node(
        self, state: BaseAgentState, config: RunnableConfig
    ) -> dict[str, Any]:
        try:
            response = self._invoke_chain(state, config)
        except Exception as e:
            return {
                MESSAGES: [
                    AIMessage(
                        content=f"Sorry, I encountered an error while processing the request. Error: {e}",
                        name=self.name,
                    )
                ]
            }

        # if the recursive limit is reached and the response is a tool call, return a message.
        # 'is_last_step' is a boolean that is True if the recursive limit is reached.
        if (
            state.is_last_step
            and isinstance(response, AIMessage)
            and response.tool_calls
        ):
            return {
                MESSAGES: [
                    AIMessage(
                        content="Sorry, I need more steps to process the request.",
                        name=self.name,
                    )
                ]
            }

        response.additional_kwargs["owner"] = self.name
        return {MESSAGES: [response]}

    def _finalizer_node(self, state: BaseAgentState, config: RunnableConfig) -> Any:
        """Finalizer node will mark the task as completed and clean-up extra messages."""
        state.my_task.complete()
        # clean all agent messages to avoid populating the checkpoint with unnecessary messages.
        return {
            MESSAGES: [
                RemoveMessage(id=m.id)  # type: ignore
                for m in state.messages
                if self.is_internal_message(m)
            ],
            MY_TASK: None,
        }

    def _build_graph(self, state_class: type) -> Any:
        # Define a new graph
        workflow = StateGraph(state_class)

        # Define the nodes of the graph.
        workflow.add_node("subtask_selector", self._subtask_selector_node)
        workflow.add_node("agent", self._model_node)
        workflow.add_node("tools", ToolNode(self.tools))
        workflow.add_node("finalizer", self._finalizer_node)

        # Set the entrypoint: ENTRY --> subtask_selector
        workflow.set_entry_point("subtask_selector")

        # Define the edge: subtask_selector --> (agent | end)
        workflow.add_conditional_edges("subtask_selector", subtask_selector_edge)

        # Define the edge: agent --> (tool | finalizer)
        workflow.add_conditional_edges("agent", agent_edge)

        # Define the edge: tool --> agent
        workflow.add_edge("tools", "agent")

        # Define the edge: finalizer --> END
        workflow.add_edge("finalizer", "__end__")

        return workflow.compile()
