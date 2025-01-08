from collections.abc import Sequence
from typing import Annotated

from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from agents.common.state import SubTask
from agents.reducer.reducers import new_default_summarization_reducer


class SupervisorState(BaseModel):
    """Supervisor state."""

    messages: Annotated[Sequence[BaseMessage], new_default_summarization_reducer()]
    subtasks: list[SubTask] | None = []
    next: str | None = None
    error: str | None = None
