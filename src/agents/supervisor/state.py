

from agents.common.state import BaseState, SubTask


class SupervisorState(BaseState):
    """Supervisor state."""

    subtasks: list[SubTask] | None = []
    next: str | None = None
    error: str | None = None
