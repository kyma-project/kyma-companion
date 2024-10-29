from typing import Any

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.graph.graph import CompiledGraph
from langgraph.prebuilt import ToolNode

from agents.common.constants import MESSAGES
from agents.common.state import SubTaskStatus
from agents.common.utils import filter_messages
from agents.kyma.constants import (
    GRAPH_STEP_TIMEOUT_SECONDS,
    IS_LAST_STEP,
    KYMA_AGENT,
    MY_TASK,
    OWNER,
    QUERY,
)
from agents.kyma.prompts import KYMA_AGENT_PROMPT
from agents.kyma.state import KymaAgentState
from agents.kyma.tools.query import kyma_query_tool
from agents.kyma.tools.search import search_kyma_doc_tool
from agents.kyma.utils import agent_edge, subtask_selector_edge
from utils.logging import get_logger
from utils.models import IModel

logger = get_logger(__name__)

class KymaAgent:
    """Kyma agent class."""

    _name: str = KYMA_AGENT
    model: IModel
    graph: CompiledGraph

    def __init__(self, model: IModel):
        self.tools = [search_kyma_doc_tool, kyma_query_tool]
        self.model = model
        self.chain = self._create_chain()
        self.graph = self._build_graph()
        self.graph.step_timeout = GRAPH_STEP_TIMEOUT_SECONDS

    @property
    def name(self) -> str:
        """Agent name."""
        return self._name

    def agent_node(self) -> CompiledGraph:
        """Get Kyma agent node function."""
        return self.graph

    def _create_chain(self) -> Any:
        agent_prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(KYMA_AGENT_PROMPT),
                MessagesPlaceholder(variable_name=MESSAGES),
                HumanMessage(content="query: {query}"),
            ]
        )

        return agent_prompt | self.model.llm.bind_tools(self.tools)

    def is_internal_message(self, message: BaseMessage) -> bool:
        """Check if the message is an internal message."""
        if (
            message.additional_kwargs is not None
            and OWNER in message.additional_kwargs
            and message.additional_kwargs[OWNER] == self.name
            and message.tool_calls  # type: ignore
        ):
            return True

        tool_names = [tool.name for tool in self.tools]
        if isinstance(message, ToolMessage) and message.name in tool_names:
            return True
        return False

    def _subtask_selector_node(self, state: KymaAgentState) -> dict[str, Any]:
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

    def _model_node(
        self, state: KymaAgentState, config: RunnableConfig
    ) -> dict[str, Any]:
        inputs = {
            MESSAGES: filter_messages(state.messages),
            QUERY: state.my_task.description,
        }

        try:
            response = self.chain.invoke(inputs, config)
        except Exception as e:
            return {
                MESSAGES: [
                    AIMessage(
                        content=f"Sorry, I encountered an error while processing the request. Error: {e}",
                        name=self.name,
                    )
                ]
            }

        if (
            state.is_last_step
            and isinstance(response, AIMessage)
            and response.tool_calls
        ):
            return {
                MESSAGES: [
                    AIMessage(
                        content="Sorry, the Kyma agent needs more steps to process the request.",
                        name=self.name,
                    )
                ]
            }

        response.additional_kwargs[OWNER] = self.name
        return {MESSAGES: [response]}

    def _finalizer_node(
        self, state: KymaAgentState, config: RunnableConfig
    ) -> dict[str, Any]:
        """Finalizer node will mark the task as completed and clean-up extra messages."""
        state.my_task.complete()

        return {
            MESSAGES: [
                RemoveMessage(id=m.id)  # type: ignore
                for m in state.messages
                if self.is_internal_message(m)
            ],
            MY_TASK: None,
        }

    def _build_graph(self) -> CompiledGraph:
        # Define a new graph
        workflow = StateGraph(KymaAgentState)

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
