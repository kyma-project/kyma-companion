"""Tests for HookChain."""

import asyncio

import pytest

from agents.hooks.base import HookResult
from agents.hooks.chain import HookChain


class _BlockingHook:
    async def run(self, query: str, history: list[dict]) -> HookResult:
        return HookResult(blocked=True, direct_response="blocked by hook")


class _PassthroughHook:
    async def run(self, query: str, history: list[dict]) -> HookResult:
        return HookResult(blocked=False)


class TestHookChain:
    @pytest.mark.asyncio
    async def test_empty_chain_passes(self):
        chain = HookChain([])
        result = await chain.run("hello", [])
        assert result.blocked is False

    @pytest.mark.asyncio
    async def test_all_pass_through(self):
        chain = HookChain([_PassthroughHook(), _PassthroughHook()])
        result = await chain.run("what is kyma?", [])
        assert result.blocked is False

    @pytest.mark.asyncio
    async def test_first_hook_blocks(self):
        chain = HookChain([_BlockingHook(), _PassthroughHook()])
        result = await chain.run("bad query", [])
        assert result.blocked is True
        assert result.direct_response == "blocked by hook"

    @pytest.mark.asyncio
    async def test_second_hook_blocks(self):
        chain = HookChain([_PassthroughHook(), _BlockingHook()])
        result = await chain.run("bad query", [])
        assert result.blocked is True
        assert result.direct_response == "blocked by hook"

    @pytest.mark.asyncio
    async def test_both_block_first_by_index_wins(self):
        """When multiple hooks block simultaneously, the lowest-index one wins."""

        class _BlockingHookA:
            async def run(self, query: str, history: list[dict]) -> HookResult:
                return HookResult(blocked=True, direct_response="blocked by A")

        class _BlockingHookB:
            async def run(self, query: str, history: list[dict]) -> HookResult:
                return HookResult(blocked=True, direct_response="blocked by B")

        chain = HookChain([_BlockingHookA(), _BlockingHookB()])
        result = await chain.run("bad query", [])
        assert result.blocked is True
        assert result.direct_response == "blocked by A"

    @pytest.mark.asyncio
    async def test_fail_fast_cancels_slow_hook(self):
        """A fast blocking hook causes the slow hook to be cancelled early."""
        slow_hook_completed = False

        class _FastBlockingHook:
            async def run(self, query: str, history: list[dict]) -> HookResult:
                return HookResult(blocked=True, direct_response="fast block")

        class _SlowPassthroughHook:
            async def run(self, query: str, history: list[dict]) -> HookResult:
                nonlocal slow_hook_completed
                await asyncio.sleep(10)
                slow_hook_completed = True
                return HookResult(blocked=False)

        chain = HookChain([_FastBlockingHook(), _SlowPassthroughHook()])
        result = await chain.run("bad query", [])

        assert result.blocked is True
        assert not slow_hook_completed

    @pytest.mark.asyncio
    async def test_hooks_run_in_parallel(self):
        """Both hooks must start before either finishes."""
        started: list[str] = []
        finished: list[str] = []

        class _SlowHook:
            def __init__(self, name: str):
                self._name = name

            async def run(self, query: str, history: list[dict]) -> HookResult:
                started.append(self._name)
                await asyncio.sleep(0.05)
                finished.append(self._name)
                return HookResult(blocked=False)

        chain = HookChain([_SlowHook("A"), _SlowHook("B")])
        await chain.run("query", [])

        assert set(started) == {"A", "B"}
        assert set(finished) == {"A", "B"}
        # Both started before either finished
        assert len(started) == 2  # noqa: PLR2004
        assert started[0] in {"A", "B"} and started[1] in {"A", "B"}
