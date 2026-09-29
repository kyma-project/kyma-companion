"""Two LLM passes per turn: classify the query (9 categories) and judge the
response quality (3 outcomes), using Claude Sonnet 4.6 via gen-ai-hub. Prompts and
schema are lifted from the PoC notebooks. Token usage is accumulated across calls.
"""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from conversation_segmentation.taxonomy import Category, Judgement

_CATEGORY_VALUES = ", ".join(c.value for c in Category)

_CLASSIFY_SYSTEM = (
    "You are a Kyma and Kubernetes expert. Your task is to classify the user's query "
    "into ONE of the predefined categories. If unsure pick 'other'.\n\n"
    f"Categories: {_CATEGORY_VALUES}\n\n"
    "Important rules:\n1. Overweight the user query than resource information.\n"
)

_JUDGE_SYSTEM = (
    "You are an AI Judge tasked with evaluating whether a response sufficiently answers a "
    "user's query related to Kyma or Kubernetes. You are also a Kyma and Kubernetes expert.\n\n"
    "## Your Task\nAnalyze the user query and the provided agent response, then determine if the "
    "agent response adequately addresses the user query. Think step-by-step.\n\n"
    "## Evaluation Criteria\nRelevance, Completeness, Accuracy, Clarity, Directness.\n\n"
    "## Guidelines\n- Be objective. A response can be PARTIAL if it addresses some but not all "
    "aspects. Minor imperfections don't necessarily make a response insufficient."
)


class Classification(BaseModel):
    """Classify the user's Kyma/Kubernetes query into exactly one category."""

    category: Category = Field(description="The single best-fitting category")


class JudgementResponse(BaseModel):
    """Judgement of whether the response sufficiently answers the query."""

    judgement: Judgement = Field(description="evaluation outcome")
    reasoning: str = Field(description="brief explanation (not persisted)")


class Segmenter:
    """Bind the classify/judge chains to a LangChain chat model."""

    def __init__(self, classify: Any, judge: Any) -> None:
        self._classify = classify
        self._judge = judge
        self.tokens: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    @classmethod
    def build(cls, model_llm: Any) -> Segmenter:
        """Construct structured classify and judge runnables from a LangChain LLM."""
        classify_prompt = ChatPromptTemplate.from_messages([("system", _CLASSIFY_SYSTEM), ("human", "Query: {query}")])
        judge_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", _JUDGE_SYSTEM),
                (
                    "human",
                    "Evaluate user query and agent response.\n\n"
                    "**user query**: {query}\n\n**agent response**: {response}",
                ),
            ]
        )
        classify = classify_prompt | model_llm.with_structured_output(
            Classification, method="function_calling", include_raw=True
        )
        judge = judge_prompt | model_llm.with_structured_output(
            JudgementResponse, method="function_calling", include_raw=True
        )
        return cls(classify, judge)

    def _tally(self, raw: Any) -> None:
        """Accumulate token usage from a structured output's raw message."""
        usage = getattr(raw, "usage_metadata", None) or {}
        self.tokens["prompt_tokens"] += int(usage.get("input_tokens", 0))
        self.tokens["completion_tokens"] += int(usage.get("output_tokens", 0))
        self.tokens["total_tokens"] += int(usage.get("total_tokens", 0))

    async def segment_turn(self, query: str, response: str) -> tuple[Category, Judgement]:
        """Classify + judge one turn. Raises on any LLM/parse error (caller counts it)."""
        c = await self._classify.ainvoke({"query": query})
        self._tally(c["raw"])
        j = await self._judge.ainvoke({"query": query, "response": response})
        self._tally(j["raw"])
        return c["parsed"].category, j["parsed"].judgement
