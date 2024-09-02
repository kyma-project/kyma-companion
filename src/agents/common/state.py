import operator
from collections.abc import Sequence
from enum import Enum
from typing import Annotated

from langchain_core.messages import BaseMessage
from langchain_core.pydantic_v1 import BaseModel, Field


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


class AgentState(BaseModel):
    """Agent state.

    Attributes:
        input: UserInput: user input with user query and resource(s) contextual information
        messages: list[BaseMessage]: messages exchanged between agents and user
        next: str: next LangGraph node to be called. It can be KymaAgent, KubernetesAgent, or Finalizer.
        subtasks: list[SubTask]: different steps/subtasks to follow
        final_response: str: final response to the user
        error: str: error message if error occurred

    """

    input: UserInput | None = Field(
        description="user input with user query and resource(s) contextual information"
    )

    messages: Annotated[Sequence[BaseMessage], operator.add]
    next: str | None
    subtasks: list[SubTask] | None = []
    final_response: str | None = ""
    error: str | None

    def all_tasks_completed(self) -> bool:
        """Check if all the sub-tasks are completed."""
        return all(task.status == SubTaskStatus.COMPLETED for task in self.subtasks)


class Plan(BaseModel):
    """Plan to follow in future"""

    subtasks: list[SubTask] = Field(
        description="different steps/subtasks to follow, should be in sorted order"
    )
