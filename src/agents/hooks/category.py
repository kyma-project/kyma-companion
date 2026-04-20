"""CategoryHook — classifies query and returns direct responses for non-technical queries."""

from __future__ import annotations

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from agents.common.constants import RESPONSE_HELLO, RESPONSE_QUERY_OUTSIDE_DOMAIN
from agents.hooks.base import HookResult
from agents.hooks.prompts import CATEGORY_HOOK_PROMPT
from utils.logging import get_logger
from utils.models.factory import IModel

logger = get_logger(__name__)


class CategoryCheckResponse(BaseModel):
    """Structured output for the category hook LLM call."""

    category: Literal["Kyma", "Kubernetes", "Programming", "About You", "Greeting", "Irrelevant"] = Field(
        description="""
        Classify the user query into one of:
        - "Kyma": related to Kyma (interpret "function" as Kyma Function, "Subscription" as Kyma Subscription)
        - "Kubernetes": related to Kubernetes
        - "Programming": programming question NOT specific to Kyma or Kubernetes
        - "About You": question about you (Joule) and your capabilities
        - "Greeting": social pleasantry (Hello, Hi, How are you, Good morning, etc.)
        - "Irrelevant": all other queries (geography, history, science, entertainment, etc.)
        """
    )

    direct_response: str = Field(
        default="",
        description="""
        If category is "Programming" or "About You", generate a direct response to the user query.
        Otherwise return empty string.
        """,
    )


class CategoryHook:
    """Classifies the query and short-circuits for non-technical or handled categories."""

    def __init__(self, model: IModel) -> None:
        self._chain = model.llm.with_structured_output(CategoryCheckResponse, method="function_calling")

    async def run(self, query: str, history: list[dict]) -> HookResult:
        """Classify query and return a direct response or forward to the main agent."""
        messages = [
            SystemMessage(content=CATEGORY_HOOK_PROMPT),
            HumanMessage(content=query),
        ]
        try:
            result: CategoryCheckResponse = await self._chain.ainvoke(messages)
            logger.debug(f"CategoryHook classified query as: {result.category}")

            if result.category == "Greeting":
                return HookResult(blocked=True, direct_response=RESPONSE_HELLO)

            if result.category in ("Programming", "About You") and result.direct_response:
                return HookResult(blocked=True, direct_response=result.direct_response)

            if result.category in ("Kyma", "Kubernetes"):
                return HookResult(blocked=False)

            # Irrelevant or unmatched
            return HookResult(blocked=True, direct_response=RESPONSE_QUERY_OUTSIDE_DOMAIN)

        except Exception:
            logger.exception("CategoryHook LLM call failed — forwarding to agent")
            return HookResult(blocked=False)
