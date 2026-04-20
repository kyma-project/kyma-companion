"""Pre-hook base types: HookResult and IHook protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class HookResult:
    """Result returned by a pre-hook."""

    blocked: bool
    direct_response: str = ""


class IHook(Protocol):
    """Protocol for pre-hooks that run before the main agent."""

    async def run(self, query: str, history: list[dict]) -> HookResult:
        """Evaluate the query and return a HookResult."""
        ...
