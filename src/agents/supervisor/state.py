from collections.abc import Sequence
from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from pydantic import BaseModel

from agents.common.state import BaseState, SubTask


class SupervisorState(BaseState):
    """Supervisor state."""

    subtasks: list[SubTask] | None = []
    next: str | None = None
    error: str | None = None
