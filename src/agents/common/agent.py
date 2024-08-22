from typing import Any, Protocol

from agents.common.state import AgentState


class Agent(Protocol):
    """Agent interface."""

    def agent_node(self, state: AgentState) -> dict[str, Any]:
        """Agent node."""
        ...
