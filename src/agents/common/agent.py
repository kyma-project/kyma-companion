from typing import Any, Literal, Protocol

from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from agents.common.constants import (
    AGENT_MESSAGES,
    ERROR,
    MESSAGES,
)
from agents.common.state import BaseAgentState
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

    def _get_user_query(self, state: BaseAgentState) -> str:
        """Extract the user query from messages."""
        for msg in reversed(state.messages):
            if isinstance(msg, HumanMessage):
                return msg.content
        return ""

    async def _invoke_chain(self, state: BaseAgentState, config: RunnableConfig) -> Any:
        input_messages = state.get_agent_messages_including_summary()
        if len(state.agent_messages) == 0:
            input_messages = filter_messages(state.messages)

        filter_valid_messages_list = filter_valid_messages(input_messages)
        response = await ainvoke_chain(
            self.chain,
            {
                AGENT_MESSAGES: filter_valid_messages_list,
                "query": self._get_user_query(state),
            },
            config=config,
        )
        return response

    def _handle_recursive_limit_error(self, state: BaseAgentState) -> dict[str, Any]:
        """Handle recursive limit error."""
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
        if state.k8s_client is None:
            raise ValueError("Kubernetes client is not initialized.")

        if state.remaining_steps <= AGENT_STEPS_NUMBER:
            return self._handle_recursive_limit_error(state)

        response, error_response = await self._invoke_chain_with_error_handling(state, config)
        if error_response:
            return error_response

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
        """Finalizer node: propagates the agent's final response to the parent graph messages."""
        last_content = ""
        if (
            hasattr(state, "agent_messages")
            and state.agent_messages
            and isinstance(state.agent_messages, list)
            and len(state.agent_messages) > 0
            and state.agent_messages[-1]
            and hasattr(state.agent_messages[-1], "content")
        ):
            last_content = state.agent_messages[-1].content or ""

        return {
            MESSAGES: [
                AIMessage(
                    content=last_content,
                    name=self.name,
                    id=state.agent_messages[-1].id if state.agent_messages else None,
                )
            ],
        }

    def _build_graph(self, state_class: type) -> CompiledStateGraph:
        workflow: StateGraph = StateGraph(state_class)

        workflow.add_node("agent", self._model_node)
        tool_node = ToolNode(tools=self.tools, messages_key=AGENT_MESSAGES, handle_tool_errors=True)
        workflow.add_node("tools", tool_node)
        workflow.add_node("finalizer", self._finalizer_node)

        workflow.set_entry_point("agent")

        workflow.add_conditional_edges("agent", agent_edge)
        workflow.add_edge("tools", "agent")
        workflow.add_edge("finalizer", "__end__")

        return workflow.compile()
