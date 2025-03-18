from collections.abc import Sequence
from enum import Enum
from typing import Annotated, Any, Literal, cast

from langchain_core.messages import (
    BaseMessage,
    SystemMessage,
)
from langgraph.graph import add_messages
from langgraph.managed import IsLastStep, RemainingSteps
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict

from agents.common.constants import COMMON, K8S_AGENT, K8S_CLIENT, KYMA_AGENT
from agents.common.data import Message

from agents.common.constants import COMMON, K8S_AGENT, KYMA_AGENT
from services.k8s import IK8sClient
from utils.utils import to_sequence_messages


class SubTaskStatus(str, Enum):
    """Status of the sub-task."""

    PENDING = "pending"
    COMPLETED = "completed"
    ERROR = "error"


class GatekeeperResponse(BaseModel):
    """Gatekeeper response data model."""

    direct_response: Annotated[str, Field(description="For direct response.")]
    forward_query: Annotated[
        bool,
        Field(
            default=False,
            description="For forwarding query",
        ),
    ]


class SubTask(BaseModel):
    """Sub-task data model."""

    description: Annotated[
        str,
        Field(description="user query with original wording for the assigned agent"),
    ]
    task_title: Annotated[
        str,
        Field(
            description="""Generate a title of 4 to 5 words, only use these:
          'Retrieving', 'Fetching', 'Extracting' or 'Checking'. Never use 'Creating'."""
        ),
    ]
    assigned_to: Literal[KYMA_AGENT, K8S_AGENT, COMMON]  # type: ignore
    status: str = Field(default=SubTaskStatus.PENDING)

    def complete(self) -> None:
        """Update the result of the task."""
        self.status = SubTaskStatus.COMPLETED

    def completed(self) -> bool:
        """Check if the task is completed."""
        return self.status == SubTaskStatus.COMPLETED

    def is_pending(self) -> bool:
        """Check if the task is pending."""
        return self.status == SubTaskStatus.PENDING

    def is_error(self) -> bool:
        """Check if the task is error status."""
        return self.status == SubTaskStatus.ERROR


# After upgrading generative-ai-hub-sdk we can message that use pydantic v2
# Currently, we are using pydantic v1.
class ResourceInformation(BaseModel):
    """K8s/Kyma resource information."""

    resource_kind: str | None = None
    resource_api_version: str | None = None
    resource_name: str | None = None
    namespace: str | None = None

    @classmethod
    def from_message(cls, message: Message) -> "ResourceInformation":
        return cls(
            resource_kind=message.resource_kind,
            resource_api_version=message.resource_api_version,
            resource_name=message.resource_name,
            namespace=message.namespace,
        )


class Plan(BaseModel):
    """Plan to follow in future"""

    subtasks: list[SubTask] | None = Field(
        description="different subtasks for user query, should be in sorted order"
    )


class BaseState(BaseModel):
    """Base state for all states."""

    messages: Annotated[Sequence[BaseMessage], add_messages]
    resource_information: Annotated[
        ResourceInformation, lambda old, new: new or old or None
    ]


class CompanionState(BaseState):
    """State for the main companion graph.

    Attributes:
        input: ResourceInformation: Kubernetes/Kyma resource(s) information
        messages: list[BaseMessage]: messages exchanged between agents and user
        next: str: next LangGraph node to be called. It can be KymaAgent, KubernetesAgent, or Finalizer.
        subtasks: list[SubTask]: different steps/subtasks to follow
        error: str: error message if error occurred
        k8s_client: IK8sClient: Kubernetes client for fetching data from the cluster

    """

    thread_owner: str = ""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    messages_summary: str = ""
    next: str | None = None
    subtasks: list[SubTask] | None = []
    error: str | None = None
    k8s_client: Annotated[IK8sClient | None, Field(default=None, exclude=True)]

    # Model config for pydantic.
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def get_messages_including_summary(self) -> Sequence[BaseMessage]:
        """Get messages including the summary message."""
        if self.messages_summary:
            return to_sequence_messages(
                add_messages(
                    SystemMessage(content=self.messages_summary),
                    cast(
                        list[
                            BaseMessage
                            | list[str]
                            | tuple[str, str]
                            | str
                            | dict[str, Any]
                        ],
                        self.messages,
                    ),
                )
            )
        return self.messages


class BaseAgentState(BaseState):
    """Base state for KymaAgent and KubernetesAgent agents (subgraphs)."""

    messages: Annotated[Sequence[BaseMessage], add_messages]
    subtasks: list[SubTask] | None = []
    k8s_client: Annotated[IK8sClient | None, Field(default=None, exclude=True)]

    # Subgraph private fields
    agent_messages: Annotated[Sequence[BaseMessage], add_messages]
    agent_messages_summary: str = ""
    my_task: SubTask | None = None
    is_last_step: IsLastStep
    error: str | None = None
    remaining_steps: RemainingSteps

    # Model config for pydantic.
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def get_agent_messages_including_summary(self) -> Sequence[BaseMessage]:
        """Get messages including the summary message."""
        if self.agent_messages_summary:
            return to_sequence_messages(
                add_messages(
                    SystemMessage(content=self.agent_messages_summary),
                    cast(
                        list[
                            BaseMessage
                            | list[str]
                            | tuple[str, str]
                            | str
                            | dict[str, Any]
                        ],
                        self.agent_messages,
                    ),
                )
            )
        return self.agent_messages
