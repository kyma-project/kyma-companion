"""One structured LLM pass per turn: classify what the user's turn is about.

We extract what the conversation is about so distinct Kyma problem areas can be
counted; we do not measure answer quality. The model returns a controlled area/intent
plus a short free-text capability, a human-readable topic label, and a one-sentence
generic summary.

``reasoning`` is requested to improve the classification but is never returned to the
caller or persisted. The capability, topic label, and summary are additionally scrubbed
downstream (``canonicalizer``) before anything is stored.
"""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from conversation_segmentation.canonicalizer import CanonicalTopic, canonicalize
from conversation_segmentation.taxonomy import Area, Intent

_AREA_VALUES = ", ".join(a.value for a in Area)
_INTENT_VALUES = ", ".join(i.value for i in Intent)

_SYSTEM = (
    "You are a Kyma and Kubernetes expert analysing a single support conversation turn "
    "(a user query and the assistant's answer). Identify what the user's turn is ABOUT "
    "so similar conversations can be grouped and counted. Do not judge answer quality.\n\n"
    f"Pick exactly one area from: {_AREA_VALUES}. Use 'other' only when none fit.\n"
    f"Pick exactly one intent from: {_INTENT_VALUES}.\n"
    "Give a short 'capability' (1-3 words) naming the specific feature or sub-area, for "
    "example 'mtls', 'traffic management', 'function build', 'apirule auth'.\n"
    "Give a short human-readable 'topic' label.\n"
    "Give a ONE-sentence generic 'summary' of what the user wanted, for example "
    "'user was configuring mTLS between two workloads'.\n"
    "The 'capability', 'topic', and 'summary' MUST NOT contain names, namespaces, "
    "resource names, URLs, IP addresses, IDs, tokens, or error payloads. Describe only "
    "the subject.\n"
    "Set 'confidence' between 0 and 1. Use area 'other' when you are not confident."
)


class TurnTopic(BaseModel):
    """Structured description of what one conversation turn is about."""

    area: Area = Field(description="single best-fitting product area")
    intent: Intent = Field(description="what the user was trying to do")
    capability: str = Field(description="short specific feature/sub-area, 1-3 words")
    topic: str = Field(description="short human-readable topic label")
    summary: str = Field(description="one generic sentence; no identifiers or payloads")
    confidence: float = Field(ge=0, le=1, description="0-1 confidence in this classification")
    reasoning: str = Field(default="", description="brief rationale (never persisted)")


class Segmenter:
    """Bind the topic-classification chain to a LangChain chat model."""

    def __init__(self, classify: Any) -> None:
        self._classify = classify
        self.tokens: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    @classmethod
    def build(cls, model_llm: Any) -> Segmenter:
        """Construct the structured topic-classification runnable from a LangChain LLM."""
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", _SYSTEM),
                ("human", "**user query**: {query}\n\n**assistant answer**: {response}"),
            ]
        )
        classify = prompt | model_llm.with_structured_output(TurnTopic, method="function_calling", include_raw=True)
        return cls(classify)

    def _tally(self, raw: Any) -> None:
        """Accumulate token usage from a structured output's raw message."""
        usage = getattr(raw, "usage_metadata", None) or {}
        self.tokens["prompt_tokens"] += int(usage.get("input_tokens", 0))
        self.tokens["completion_tokens"] += int(usage.get("output_tokens", 0))
        self.tokens["total_tokens"] += int(usage.get("total_tokens", 0))

    async def segment_turn(self, query: str, response: str) -> CanonicalTopic:
        """Classify one turn and return its canonical, privacy-safe topic assignment.

        Raises on any LLM/parse error so the caller can count it as a failed turn.
        """
        result = await self._classify.ainvoke({"query": query, "response": response})
        self._tally(result["raw"])
        parsed: TurnTopic = result["parsed"]
        return canonicalize(
            area=parsed.area,
            intent=parsed.intent,
            capability=parsed.capability,
            topic=parsed.topic,
            summary=parsed.summary,
            confidence=parsed.confidence,
        )
