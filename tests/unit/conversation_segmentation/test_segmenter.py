"""Tests for the topic segmenter (single structured pass with token accounting)."""

from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage
from pydantic import ValidationError

from conversation_segmentation.segmenter import Segmenter, TurnTopic
from conversation_segmentation.taxonomy import Area, Intent

pytestmark = pytest.mark.unit


def _raw(inp, out):
    """Create a mock AIMessage with usage_metadata."""
    return AIMessage(content="", usage_metadata={"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out})


@pytest.mark.asyncio
async def test_segment_turn_canonicalizes_and_tallies_tokens():
    seg = Segmenter.__new__(Segmenter)
    classify_mock = AsyncMock()
    classify_mock.ainvoke.return_value = {
        "parsed": TurnTopic(
            area=Area.ISTIO,
            intent=Intent.TROUBLESHOOTING,
            capability="mTLS",
            topic="mTLS not working",
            summary="user's mTLS stopped working in namespace: prod-1",
            confidence=0.9,
            reasoning="should never be persisted",
        ),
        "raw": _raw(10, 5),
    }
    seg._classify = classify_mock
    seg.tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    result = await seg.segment_turn("why is mtls broken?", "check peer auth")

    assert result.topic_key == "istio/troubleshooting/mtls"
    assert "prod-1" not in result.summary  # sanitized
    assert seg.tokens == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}


@pytest.mark.parametrize("bad_confidence", [-0.1, 1.1])
def test_turn_topic_rejects_out_of_range_confidence(bad_confidence):
    with pytest.raises(ValidationError):
        TurnTopic(
            area=Area.ISTIO,
            intent=Intent.TROUBLESHOOTING,
            capability="mTLS",
            topic="mTLS not working",
            summary="generic summary",
            confidence=bad_confidence,
        )
