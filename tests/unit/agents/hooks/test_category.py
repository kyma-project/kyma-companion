"""Tests for CategoryHook."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.common.constants import RESPONSE_HELLO, RESPONSE_QUERY_OUTSIDE_DOMAIN
from agents.hooks.category import CategoryCheckResponse, CategoryHook


def _make_model(response: CategoryCheckResponse) -> MagicMock:
    chain = MagicMock()
    chain.ainvoke = AsyncMock(return_value=response)
    llm = MagicMock()
    llm.with_structured_output.return_value = chain
    model = MagicMock()
    model.llm = llm
    return model


@pytest.mark.parametrize(
    "category,direct_response,expect_blocked,expect_content",
    [
        ("Kyma", "", False, ""),
        ("Kubernetes", "", False, ""),
        ("Greeting", "", True, RESPONSE_HELLO),
        ("Irrelevant", "", True, RESPONSE_QUERY_OUTSIDE_DOMAIN),
        ("Programming", "Here is how you do X in Python.", True, "Here is how you do X in Python."),
        ("About You", "I am Joule.", True, "I am Joule."),
        # Programming/About You with empty direct_response → outside domain
        ("Programming", "", True, RESPONSE_QUERY_OUTSIDE_DOMAIN),
    ],
)
@pytest.mark.asyncio
async def test_category_routing(category, direct_response, expect_blocked, expect_content):
    model = _make_model(CategoryCheckResponse(category=category, direct_response=direct_response))
    hook = CategoryHook(model)
    result = await hook.run("some query", [])
    assert result.blocked is expect_blocked
    if expect_content:
        assert result.direct_response == expect_content


class TestCategoryHookEdgeCases:
    @pytest.mark.asyncio
    async def test_llm_failure_forwards_to_agent(self):
        """On LLM error, hook should fail open (forward to CompanionAgent)."""
        chain = MagicMock()
        chain.ainvoke = AsyncMock(side_effect=RuntimeError("LLM error"))
        llm = MagicMock()
        llm.with_structured_output.return_value = chain
        model = MagicMock()
        model.llm = llm

        hook = CategoryHook(model)
        result = await hook.run("what pods are running?", [])
        assert result.blocked is False
