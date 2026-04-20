"""HookChain — runs all IHook instances in parallel with fail-fast on first block."""

from __future__ import annotations

import asyncio

from agents.hooks.base import HookResult, IHook
from utils.logging import get_logger

logger = get_logger(__name__)


class HookChain:
    """Runs all hooks in parallel; returns as soon as any hook blocks.

    If a completed hook passes, waits for the remaining hooks. If no hook
    blocks, returns HookResult(blocked=False). When multiple hooks block
    simultaneously, the one earliest in the list wins.
    """

    def __init__(self, hooks: list[IHook]) -> None:
        self._hooks = hooks

    async def run(self, query: str, history: list[dict]) -> HookResult:
        """Run all hooks in parallel, failing fast when any hook blocks."""
        if not self._hooks:
            return HookResult(blocked=False)

        tasks = {
            asyncio.create_task(hook.run(query, history)): i
            for i, hook in enumerate(self._hooks)
        }
        pending = set(tasks)
        results: dict[int, HookResult] = {}

        try:
            while pending:
                done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)

                for task in done:
                    results[tasks[task]] = task.result()

                # Check if any completed task blocked — pick lowest index among them
                blocking = {idx: r for idx, r in results.items() if r.blocked}
                if blocking:
                    winner_idx = min(blocking)
                    winner = blocking[winner_idx]
                    logger.debug(f"Hook {self._hooks[winner_idx].__class__.__name__} blocked the request")
                    return winner

        finally:
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

        return HookResult(blocked=False)
