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

    def update_result(self, result: str) -> None:
        """Update the result of the task."""
        self.result = result
        self.status = SubTaskStatus.COMPLETED


class AgentState(BaseModel):
    """Agent state."""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    next: str | None
    subtasks: list[SubTask] | None = []
    final_response: str | None = ""

    def all_tasks_completed(self) -> bool:
        """Check if all the sub-tasks are completed."""
        return all(task.status == SubTaskStatus.COMPLETED for task in self.subtasks)


class Plan(BaseModel):
    """Plan to follow in future"""

    subtasks: list[SubTask] = Field(
        description="different steps/subtasks to follow, should be in sorted order"
    )
