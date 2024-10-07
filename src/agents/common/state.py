from collections.abc import Sequence
from enum import Enum
from typing import Annotated

from langchain_core.messages import BaseMessage
from langchain_core.pydantic_v1 import BaseModel, Field
from langgraph.graph import add_messages

from services.k8s import IK8sClient


class SubTaskStatus(str, Enum):
    """Status of the sub-task."""

    PENDING = "pending"
    COMPLETED = "completed"


class SubTask(BaseModel):
    """Sub-task data model."""

    description: str = Field(description="description of the task")
    assigned_to: str = Field(description="agent to whom the task is assigned")
    status: str = Field(default=SubTaskStatus.PENDING)
    result: str | None

    def complete(self) -> None:
        """Update the result of the task."""
        self.status = SubTaskStatus.COMPLETED


# After upgrading generative-ai-hub-sdk we can message that use pydantic v2
# Currently, we are using pydantic v1.
class UserInput(BaseModel):
    """User input data model."""

    query: str
    resource_kind: str | None
    resource_api_version: str | None
    resource_name: str | None
    namespace: str | None

    def get_resource_information(self) -> dict[str, str]:
        """Get resource information."""
        result = {}
        if self.resource_kind is not None and self.resource_name != "":
            result["resource_kind"] = self.resource_kind
        if self.resource_api_version is not None and self.resource_api_version != "":
            result["resource_api_version"] = self.resource_api_version
        if self.resource_name is not None and self.resource_name != "":
            result["resource_name"] = self.resource_name
        if self.namespace is not None and self.namespace != "":
            result["resource_namespace"] = self.namespace
        return result

    def is_same_resource(self, target: 'UserInput') -> bool:
        if self.resource_kind != target.resource_kind:
            return False
        if self.resource_api_version != target.resource_api_version:
            return False
        if self.resource_name != target.resource_name:
            return False
        if self.namespace != target.namespace:
            return False
        return True


class AgentState(BaseModel):
    """Agent state.

    Attributes:
        input: UserInput: user input with user query and resource(s) contextual information
        messages: list[BaseMessage]: messages exchanged between agents and user
        next: str: next LangGraph node to be called. It can be KymaAgent, KubernetesAgent, or Finalizer.
        subtasks: list[SubTask]: different steps/subtasks to follow
        final_response: str: final response to the user
        error: str: error message if error occurred
        k8s_client: IK8sClient: Kubernetes client for fetching data from the cluster

    """

    input: UserInput | None = Field(
        description="user input with user query and resource(s) contextual information"
    )

    # add_messages is better than operator.add, because it sets the id of messages if missing.
    messages: Annotated[Sequence[BaseMessage], add_messages]
    next: str | None
    subtasks: list[SubTask] | None = []
    final_response: str | None = ""
    error: str | None
    # IK8sClient interface implements the method "model_dump" which returns None, so that no confidential
    # information is stored in the checkpoint.
    k8s_client: IK8sClient | None = None

    def all_tasks_completed(self) -> bool:
        """Check if all the sub-tasks are completed."""
        return all(task.status == SubTaskStatus.COMPLETED for task in self.subtasks)

    class Config:
        arbitrary_types_allowed = True
        fields = {"k8s_client": {"exclude": True}}


class Plan(BaseModel):
    """Plan to follow in future"""

    subtasks: list[SubTask] | None = Field(
        description="different steps/subtasks to follow, should be in sorted order"
    )

    response: str | None = Field(
        description="direct response of planner if plan is unnecessary"
    )
