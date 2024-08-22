from typing import Protocol


class Agent(Protocol):
    """Agent interface."""

    def agent_node(self):  # noqa ANN
        """Agent node."""
        ...

    @property
    def name(self) -> str:
        """Agent name."""
        ...
