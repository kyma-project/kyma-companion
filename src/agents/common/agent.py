from typing import Any, Literal, Protocol

from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from agents.common.constants import (
    AGENT_MESSAGES,
    ERROR,
    IS_LAST_STEP,
    MESSAGES,
    MY_TASK,
    SUBTASKS,
)
from agents.common.state import BaseAgentState, SubTaskStatus
from agents.common.utils import (
    filter_messages,
    filter_valid_messages,
)
from utils.chain import ainvoke_chain
from utils.logging import get_logger
from utils.models.factory import IModel
from utils.settings import GRAPH_STEP_TIMEOUT_SECONDS

logger = get_logger(__name__)


AGENT_STEPS_NUMBER = 3


def subtask_selector_edge(state: BaseAgentState) -> Literal["agent", "finalizer"]:
    """Function that determines whether to finalize or call agent."""
    if state.is_last_step and state.my_task is None:
        return "finalizer"
    return "agent"


def agent_edge(state: BaseAgentState) -> Literal["tools", "finalizer"]:
    """Route to tool execution or finalizer based on the last agent message."""
    last_message = state.agent_messages[-1]
    if isinstance(last_message, AIMessage) and not last_message.tool_calls:
        return "finalizer"
    return "tools"


class IAgent(Protocol):
    """Agent interface."""

    def agent_node(self) -> CompiledStateGraph:
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
        agent_prompt: ChatPromptTemplate,
        state_class: type,
    ):
        self._name = name
        self.model = model
        self.tools = tools
        self.chain = self._create_chain(agent_prompt)
        self.graph = self._build_graph(state_class)
        self.graph.step_timeout = GRAPH_STEP_TIMEOUT_SECONDS

    @property
    def name(self) -> str:
        """Agent name."""
        return self._name

    def agent_node(self) -> CompiledStateGraph:
        """Get agent node function."""
        return self.graph

    def _create_chain(self, agent_prompt: ChatPromptTemplate) -> Any:
        return agent_prompt | self.model.llm.bind_tools(self.tools)

    def _subtask_selector_node(self, state: BaseAgentState) -> dict[str, Any]:
        if state.k8s_client is None:
            raise ValueError("Kubernetes client is not initialized.")

        # find subtasks assigned to this agent and not completed.
        for subtask in state.subtasks:
            if subtask.assigned_to == self.name and subtask.status == SubTaskStatus.PENDING:
                return {
                    MY_TASK: subtask,
                }

        return {
            AGENT_MESSAGES: [
                AIMessage(
                    content="All my subtasks are already completed.",
                    name=self.name,
                )
            ],
            IS_LAST_STEP: True,
        }

    async def _invoke_chain(self, state: BaseAgentState, config: RunnableConfig) -> Any:
        input_messages = state.get_agent_messages_including_summary()
        if len(state.agent_messages) == 0:
            input_messages = filter_messages(state.messages)

        filter_valid_messages_list = filter_valid_messages(input_messages)
        response = await ainvoke_chain(
            self.chain,
            {
                AGENT_MESSAGES: filter_valid_messages_list,
                "query": state.my_task.description,
            },
            config=config,
        )
        return response

    def _handle_recursive_limit_error(self, state: BaseAgentState) -> dict[str, Any]:
        """Handle recursive limit error."""
        if state.my_task:
            state.my_task.status = SubTaskStatus.ERROR

        logger.error(f"Agent reached the recursive limit, steps remaining: {state.remaining_steps}.")
        return {
            AGENT_MESSAGES: [
                AIMessage(
                    content="Agent reached the recursive limit, not able to call Tools again",
                    name=self.name,
                )
            ],
        }

    async def _invoke_chain_with_error_handling(
        self,
        state: BaseAgentState,
        config: RunnableConfig,
    ) -> tuple[Any, dict[str, Any] | None]:
        """Handle model node error."""
        try:
            response = await self._invoke_chain(state, config)
            return response, None
        except Exception:
            logger.exception("An error occurred while processing the request.")
            # Update current subtask status
            if state.my_task:
                state.my_task.status = SubTaskStatus.ERROR

            error_response = {
                AGENT_MESSAGES: [
                    AIMessage(
                        content="Sorry, an unexpected error occurred while processing your request. "
                        "Please try again later.",
                        name=self.name,
                    )
                ],
                ERROR: "An error occurred while processing the request",
            }
            return None, error_response

    async def _model_node(self, state: BaseAgentState, config: RunnableConfig) -> dict[str, Any]:
        # if the recursive limit is reached, return a message.
        if state.remaining_steps <= AGENT_STEPS_NUMBER:
            return self._handle_recursive_limit_error(state)

        response, error_response = await self._invoke_chain_with_error_handling(state, config)
        if error_response:
            return error_response

        # if the recursive limit is reached and the response is a tool call, return a message.
        # 'is_last_step' is a boolean that is True if the recursive limit is reached.
        if state.is_last_step and isinstance(response, AIMessage) and response.tool_calls:
            return {
                AGENT_MESSAGES: [
                    AIMessage(
                        content="Sorry, I need more steps to process the request.",
                        name=self.name,
                    )
                ],
            }

        response.additional_kwargs["owner"] = self.name
        return {
            AGENT_MESSAGES: [response],
        }

    def _finalizer_node(self, state: BaseAgentState, config: RunnableConfig) -> Any:
        """Finalizer node will mark the task as completed."""
        if state.my_task is not None and state.my_task.status != SubTaskStatus.ERROR:
            logger.info("Agent task completed")
            state.my_task.complete()

        agent_pre_message = f"'{state.my_task.description}' , Agent Response - "
        # Check if agent_messages exists and has at least one element
        if (
            hasattr(state, "agent_messages")
            and state.agent_messages
            and isinstance(state.agent_messages, list)
            and len(state.agent_messages) > 0
            and state.agent_messages[-1]
            and hasattr(state.agent_messages[-1], "content")
        ):
            current_content = state.agent_messages[-1].content or ""
            state.agent_messages[-1].content = agent_pre_message + current_content

        # clean all agent messages to avoid populating the checkpoint with unnecessary messages.
        return {
            MESSAGES: [
                AIMessage(
                    content=state.agent_messages[-1].content,
                    name=self.name,
                    id=state.agent_messages[-1].id,
                )
            ],
            SUBTASKS: state.subtasks,
        }

    def _build_graph(self, state_class: type) -> CompiledStateGraph:
        # Define a new graph
        workflow: StateGraph = StateGraph(state_class)

        # Define nodes with async awareness
        workflow.add_node("subtask_selector", self._subtask_selector_node)
        workflow.add_node("agent", self._model_node)
        tool_node = ToolNode(tools=self.tools, messages_key=AGENT_MESSAGES, handle_tool_errors=True)
        workflow.add_node("tools", tool_node)
        workflow.add_node("finalizer", self._finalizer_node)

        # Set the entrypoint: ENTRY --> subtask_selector
        workflow.set_entry_point("subtask_selector")

        # Define the edge: subtask_selector --> (agent | end)
        workflow.add_conditional_edges("subtask_selector", subtask_selector_edge)

        # Define the edge: agent --> (tools | finalizer)
        workflow.add_conditional_edges("agent", agent_edge)

        # Define the edge: tool --> agent
        workflow.add_edge("tools", "agent")

        # Define the edge: finalizer --> END
        workflow.add_edge("finalizer", "__end__")

        return workflow.compile()
