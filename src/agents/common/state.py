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

from agents.common.constants import CLUSTER, COMMON, K8S_AGENT, KYMA_AGENT
from utils.utils import to_sequence_messages


class SubTaskStatus(str, Enum):
    """Status of the sub-task."""

    PENDING = "pending"
    COMPLETED = "completed"
    ERROR = "error"


class GatekeeperResponse(BaseModel):
    """Gatekeeper response data model."""

    direct_response: Annotated[
        str,
        Field(
            description="""
            Contains any of the following:
            - Direct response from conversation history
            - Direct response to user queries irreleant to Kyma or Kubernetes.
            - Empty string if query should be forwarded.
            """,
        ),
    ]
    forward_query: Annotated[
        bool,
        Field(
            default=False,
            description="Flag to indicate to forward queries related to Kyma or Kubernetes.",
        ),
    ]

    query_intent: Annotated[
        str,
        Field(
            description="Intent of the user query",
        ),
    ]

    category: Annotated[
        str,
        Field(
            description="Category of the user intent",
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
class UserInput(BaseModel):
    """User input data model."""

    query: str
    resource_kind: str | None = None
    resource_api_version: str | None = None
    resource_name: str | None = None
    namespace: str | None = None
    resource_scope: str | None = None
    resource_related_to: str | None = None

    def get_resource_information(self) -> dict[str, str]:
        """Get resource information."""
        result = {}
        # add detail about the resource kind.
        if self.resource_kind:
            result["resource_kind"] = self.resource_kind

        # add detail about the resource api version.
        if self.resource_api_version:
            result["resource_api_version"] = self.resource_api_version

        # add detail about the resource name.
        if self.resource_name:
            result["resource_name"] = self.resource_name

        # add detail about the namespace.
        if self.namespace:
            result["resource_namespace"] = self.namespace
        elif self.namespace == "" and self.resource_scope == "namespaced":
            result["resource_namespace"] = "default"

        # add detail about the resource scope.
        if self.resource_scope:
            result["resource_scope"] = self.resource_scope

        # add detail about the resource related to.
        if self.resource_related_to:
            result["resource_related_to"] = self.resource_related_to
        return result

    def is_cluster_overview_query(self) -> bool:
        """Check if the query is cluster overview query."""
        return self.resource_kind.lower() == CLUSTER


class Plan(BaseModel):
    """Plan to follow in future"""

    subtasks: list[SubTask] | None = Field(
        description="different subtasks for user query, should be in sorted order"
    )


class GraphInput(BaseModel):
    """Input for the companion graph."""

    messages: list[BaseMessage]
    user_input: UserInput
    k8s_client: Annotated[Any, Field(default=None, exclude=True)]
    subtasks: list[SubTask] = []
    error: str | None = None


class CompanionState(BaseModel):
    """State for the main companion graph.

    Attributes:
        input: UserInput: user input with user query and resource(s) contextual information
        messages: list[BaseMessage]: messages exchanged between agents and user
        next: str: next LangGraph node to be called. It can be KymaAgent, KubernetesAgent, or Finalizer.
        subtasks: list[SubTask]: different steps/subtasks to follow
        error: str: error message if error occurred
        k8s_client: IK8sClient: Kubernetes client for fetching data from the cluster

    """

    input: Annotated[
        UserInput | None,
        Field(
            description="user input with user query and resource(s) contextual information",
            default=None,
        ),
    ]
    thread_owner: str = ""
    messages: Annotated[Sequence[BaseMessage], add_messages]
    messages_summary: str = ""
    next: str | None = None
    subtasks: list[SubTask] | None = []
    error: str | None = None
    k8s_client: Annotated[Any, Field(default=None, exclude=True)]

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


class BaseAgentState(BaseModel):
    """Base state for KymaAgent and KubernetesAgent agents (subgraphs)."""

    messages: Annotated[Sequence[BaseMessage], add_messages]
    subtasks: list[SubTask] | None = []
    k8s_client: Annotated[Any, Field(default=None, exclude=True)]

    # Subgraph private fields
    agent_messages: Annotated[Sequence[BaseMessage], add_messages]
    agent_messages_summary: str = ""
    my_task: SubTask | None = None
    is_last_step: IsLastStep = Field(default=False)
    error: str | None = None
    remaining_steps: RemainingSteps = Field(default=RemainingSteps(25))

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
