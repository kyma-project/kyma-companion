from collections.abc import Sequence
from typing import Annotated

from langchain_core.messages import BaseMessage
from langchain_core.pydantic_v1 import BaseModel
from langgraph.graph import add_messages

from agents.common.state import SubTask


class SupervisorState(BaseModel):
    """Supervisor state."""

    messages: Annotated[Sequence[BaseMessage], add_messages]
    subtasks: list[SubTask] | None = []
    next: str | None
    error: str | None
