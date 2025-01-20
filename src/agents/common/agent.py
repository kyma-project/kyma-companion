from typing import Any, Literal, Protocol

from langchain_core.embeddings import Embeddings
from langchain_core.messages import (
    AIMessage,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from agents.common.constants import (
    AGENT_MESSAGES,
    AGENT_MESSAGES_SUMMARY,
    IS_LAST_STEP,
    MESSAGES,
    MY_TASK,
    SUMMARIZATION,
)
from agents.common.state import BaseAgentState, SubTaskStatus
from agents.common.utils import filter_messages
from agents.summarization.summarization import Summarization
from utils.models.factory import IModel, ModelType
from utils.settings import (
    SUMMARIZATION_TOKEN_LOWER_LIMIT,
    SUMMARIZATION_TOKEN_UPPER_LIMIT,
)


def subtask_selector_edge(state: BaseAgentState) -> Literal["agent", "finalizer"]:
    """Function that determines whether to finalize or call agent."""
    if state.is_last_step and state.my_task is None:
        return "finalizer"
    return "agent"


def agent_edge(state: BaseAgentState) -> Literal["tools", "finalizer"]:
    """Function that determines whether to call tools or finalizer."""
    last_message = state.agent_messages[-1]
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
        self.summarization = Summarization(
            model=model,
            tokenizer_model_type=ModelType(model.name),
            token_lower_limit=SUMMARIZATION_TOKEN_LOWER_LIMIT,
            token_upper_limit=SUMMARIZATION_TOKEN_UPPER_LIMIT,
            messages_key=AGENT_MESSAGES,
            messages_summary_key=AGENT_MESSAGES_SUMMARY,
        )
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

    def _create_chain(self, system_prompt: str) -> Any:
        agent_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder(variable_name=AGENT_MESSAGES),
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
            AGENT_MESSAGES: [
                AIMessage(
                    content="All my subtasks are already completed.",
                    name=self.name,
                )
            ],
        }

    async def _invoke_chain(self, state: BaseAgentState, config: RunnableConfig) -> Any:
        inputs = {
            AGENT_MESSAGES: state.get_agent_messages_including_summary(),
            "query": state.my_task.description,
        }
        if len(state.agent_messages) == 0:
            inputs[AGENT_MESSAGES] = filter_messages(state.messages)

        response = await self.chain.ainvoke(inputs, config)
        return response

    async def _model_node(
        self, state: BaseAgentState, config: RunnableConfig
    ) -> dict[str, Any]:
        try:
            response = await self._invoke_chain(state, config)
        except Exception as e:
            return {
                AGENT_MESSAGES: [
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
                AGENT_MESSAGES: [
                    AIMessage(
                        content="Sorry, I need more steps to process the request.",
                        name=self.name,
                    )
                ]
            }

        response.additional_kwargs["owner"] = self.name
        return {AGENT_MESSAGES: [response]}

    def _finalizer_node(self, state: BaseAgentState, config: RunnableConfig) -> Any:
        """Finalizer node will mark the task as completed."""
        if state.my_task is not None:
            state.my_task.complete()
        # clean all agent messages to avoid populating the checkpoint with unnecessary messages.
        return {MESSAGES: [state.agent_messages[-1]]}

    def _build_graph(self, state_class: type) -> Any:
        # Define a new graph
        workflow = StateGraph(state_class)

        # Define nodes with async awareness
        workflow.add_node("subtask_selector", self._subtask_selector_node)
        workflow.add_node("agent", self._model_node)
        workflow.add_node(
            "tools", ToolNode(tools=self.tools, messages_key=AGENT_MESSAGES)
        )
        workflow.add_node("finalizer", self._finalizer_node)
        workflow.add_node(SUMMARIZATION, self.summarization.summarization_node)

        # Set the entrypoint: ENTRY --> subtask_selector
        workflow.set_entry_point("subtask_selector")

        # Define the edge: subtask_selector --> (agent | end)
        workflow.add_conditional_edges("subtask_selector", subtask_selector_edge)

        # Define the edge: agent --> (tool | finalizer)
        workflow.add_conditional_edges("agent", agent_edge)

        # Define the edge: tool --> summarization
        workflow.add_edge("tools", SUMMARIZATION)
        # Define the edge: summarization --> agent
        workflow.add_edge(SUMMARIZATION, "agent")

        # Define the edge: finalizer --> END
        workflow.add_edge("finalizer", "__end__")

        return workflow.compile()
