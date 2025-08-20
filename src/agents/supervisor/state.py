from collections.abc import Sequence
from typing import Annotated, Any

from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from pydantic import BaseModel, Field

from agents.common.state import SubTask, UserInput


class SupervisorState(BaseModel):
    """Supervisor state."""

    messages: Annotated[Sequence[BaseMessage], add_messages]
    subtasks: list[SubTask] | None = []
    next: str | None = None
    error: str | None = None
    input: Annotated[
        UserInput | None,
        Field(
            description="user input with user query and resource(s) contextual information",
            default=None,
        ),
    ]
    k8s_client: Annotated[Any, Field(default=None, exclude=True)]
