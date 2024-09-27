from typing import TypedDict, Any
import operator

from decorator import append
from langgraph.graph import add_messages
from typing_extensions import Annotated
from langgraph.managed import IsLastStep
from collections.abc import Sequence
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent, ToolNode

from agents.common.state import AgentState, SubTaskStatus
from agents.common.constants import MESSAGES
from agents.common.utils import filter_messages
from agents.k8s.prompts import K8S_AGENT_PROMPT
from langchain_core.runnables.config import RunnableConfig
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from utils.logging import get_logger
from utils.models import IModel
from services.k8s import IK8sClient
from agents.k8s.tools.query import k8s_query_tool

logger = get_logger(__name__)

K8S_AGENT = "KubernetesAgent"

class KubernetesAgentState(TypedDict):
    """The state of the Kubernetes agent."""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    k8s_client: IK8sClient
    is_last_step: IsLastStep

class KubernetesAgent:
    """Kubernetes agent class."""

    _name: str = K8S_AGENT

    def __init__(self, model: IModel):
        self.model = model
        k8s_tool_node = ToolNode([k8s_query_tool])
        self.graph = create_react_agent(
            model.llm,
            tools=k8s_tool_node,
            state_schema=KubernetesAgentState,
            state_modifier=K8S_AGENT_PROMPT,
        )

    @property
    def name(self) -> str:
        """Agent name."""
        return self._name

    def agent_node(self):  # noqa ANN
        """Get Kubernetes agent node function."""
        return self.agent_callback

    def agent_callback(self, state: AgentState, config: RunnableConfig) -> dict[str, Any]:
        if state.k8s_client is None:
            raise ValueError("Kubernetes client is not initialized.")

        # find subtasks assigned to this agent and not completed.
        subtasks = [subtask for subtask in state.subtasks if subtask.assigned_to == self.name and subtask.status != SubTaskStatus.COMPLETED]
        if len(subtasks) == 0:
            return {
                MESSAGES: [
                    AIMessage(
                        content="All my subtasks are already completed.",
                        name=self.name,
                    )
                ]
            }

        # for now, we will only process one subtask and return to supervisor.
        subtask = subtasks[0]

        # invoke the graph.
        try:
            result = self.graph.invoke(
                input={
                    "messages": add_messages(filter_messages(state.messages), HumanMessage(content=subtask.description)),
                    "k8s_client": state.k8s_client
                },
                config={
                    "configurable": {
                        "thread_id": config["metadata"]["thread_id"],
                    },
                },
                debug=False,
            )
            # mark the subtask as completed.
            subtasks[0].complete()

            # set name to the final message.
            final_message = result["messages"][-1]
            final_message.name = self.name
            return {
                MESSAGES: [final_message],
            }
        except Exception as e:
            logger.error(f"Error in agent {self.name}: {e}")
            return {
                "error": str(e),
                "next": "Exit",
            }