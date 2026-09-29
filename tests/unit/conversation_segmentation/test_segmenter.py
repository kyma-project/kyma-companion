"""Tests for the conversation segmenter (classify + judge with token accounting)."""

from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage

from conversation_segmentation.segmenter import Classification, JudgementResponse, Segmenter
from conversation_segmentation.taxonomy import Category, Judgement

pytestmark = pytest.mark.unit


def _raw(inp, out):
    """Create a mock AIMessage with usage_metadata."""
    return AIMessage(content="", usage_metadata={"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out})


@pytest.mark.asyncio
async def test_segment_turn_returns_category_and_judgement_and_tallies_tokens():
    """Segmenter.segment_turn extracts parsed values from structured outputs and tallies token usage."""
    seg = Segmenter.__new__(Segmenter)
    classify_mock = AsyncMock()
    classify_mock.ainvoke.return_value = {
        "parsed": Classification(category=Category.TROUBLESHOOTING),
        "raw": _raw(10, 2),
    }
    seg._classify = classify_mock

    judge_mock = AsyncMock()
    judge_mock.ainvoke.return_value = {
        "parsed": JudgementResponse(judgement=Judgement.PARTIAL, reasoning="x"),
        "raw": _raw(20, 3),
    }
    seg._judge = judge_mock
    seg.tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    cat, judge = await seg.segment_turn("why crash?", "because OOM")
    assert cat == Category.TROUBLESHOOTING and judge == Judgement.PARTIAL
    assert seg.tokens == {"prompt_tokens": 30, "completion_tokens": 5, "total_tokens": 35}
