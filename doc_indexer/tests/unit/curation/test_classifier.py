"""Unit tests for curation.classifier."""

import json
from unittest.mock import MagicMock, patch

import pytest
from curation.classifier import _BATCH_SIZE, classify_residue
from curation.models import CandidateDoc, CuratorConfig

pytestmark = pytest.mark.unit

_SINGLE_BATCH_COUNT = 5
_OVERFLOW_COUNT = _BATCH_SIZE + 3
_SMALL_COUNT = 3
_PAIR_COUNT = 2
_SINGLE_COUNT = 1
_EXPECTED_BATCHES_FOR_OVERFLOW = 2


def _make_candidate(repo: str = "myrepo", path: str = "docs/file.md", idx: int = 0) -> CandidateDoc:
    return CandidateDoc(
        repo=repo,
        path=path,
        h1="My Heading",
        excerpt="Some content here.",
        directory=f"/data/{repo}/docs",
        residue_reason="not_in_include_patterns",
        content_hash=f"hash{idx:04d}",
    )


def _make_decision_json(n: int) -> str:
    decisions = [
        {
            "decision": "include",
            "doc_type": "tutorial",
            "module": "eventing",
            "confidence": 0.9,
            "rationale": "user doc",
        }
        for _ in range(n)
    ]
    return json.dumps(decisions)


@pytest.fixture
def mock_llm_response():
    """A mock LLM that returns a valid JSON array for any batch."""

    def _invoke(messages):
        # Count the number of documents in the prompt to build the right-sized response
        content = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1])
        # Find the batch size from the prompt footer "exactly N elements"
        import re

        m = re.search(r"exactly (\d+) elements", content)
        n = int(m.group(1)) if m else 1
        resp = MagicMock()
        resp.content = _make_decision_json(n)
        return resp

    mock = MagicMock()
    mock.invoke.side_effect = _invoke
    return mock


class TestBatchingLogic:
    def test_single_batch_when_few_candidates(self, mock_llm_response):
        """Fewer than _BATCH_SIZE candidates -> exactly one LLM call."""
        candidates = [_make_candidate(idx=i) for i in range(_SINGLE_BATCH_COUNT)]
        config = CuratorConfig(residue_to_agent=True)

        with (
            patch("curation.classifier.get_proxy_client"),
            patch("curation.classifier.ChatOpenAI", return_value=mock_llm_response),
        ):
            results = classify_residue(candidates, config)

        assert len(results) == len(candidates)
        assert mock_llm_response.invoke.call_count == _SINGLE_COUNT

    def test_multiple_batches_when_many_candidates(self, mock_llm_response):
        """More than _BATCH_SIZE candidates -> multiple LLM calls."""
        candidates = [_make_candidate(idx=i) for i in range(_OVERFLOW_COUNT)]
        config = CuratorConfig(residue_to_agent=True)

        with (
            patch("curation.classifier.get_proxy_client"),
            patch("curation.classifier.ChatOpenAI", return_value=mock_llm_response),
        ):
            results = classify_residue(candidates, config)

        assert len(results) == len(candidates)
        assert mock_llm_response.invoke.call_count == _EXPECTED_BATCHES_FOR_OVERFLOW

    def test_exact_batch_boundary(self, mock_llm_response):
        """Exactly _BATCH_SIZE candidates -> exactly one LLM call."""
        candidates = [_make_candidate(idx=i) for i in range(_BATCH_SIZE)]
        config = CuratorConfig(residue_to_agent=True)

        with (
            patch("curation.classifier.get_proxy_client"),
            patch("curation.classifier.ChatOpenAI", return_value=mock_llm_response),
        ):
            results = classify_residue(candidates, config)

        assert len(results) == _BATCH_SIZE
        assert mock_llm_response.invoke.call_count == _SINGLE_COUNT

    def test_empty_candidates_returns_empty(self):
        """Empty input -> empty output, no LLM call."""
        config = CuratorConfig(residue_to_agent=True)

        with (
            patch("curation.classifier.get_proxy_client"),
            patch("curation.classifier.ChatOpenAI") as mock_cls,
        ):
            results = classify_residue([], config)

        assert results == []
        mock_cls.assert_not_called()


class TestFailureFallback:
    def test_model_call_exception_returns_unsure(self):
        """When the LLM raises an exception, all candidates become 'unsure'."""
        candidates = [_make_candidate(idx=i) for i in range(_SMALL_COUNT)]
        config = CuratorConfig(residue_to_agent=True)

        failing_llm = MagicMock()
        failing_llm.invoke.side_effect = RuntimeError("network error")

        with (
            patch("curation.classifier.get_proxy_client"),
            patch("curation.classifier.ChatOpenAI", return_value=failing_llm),
        ):
            results = classify_residue(candidates, config)

        assert len(results) == len(candidates)
        for r in results:
            assert r.decision == "unsure"
            assert "classifier error" in r.rationale

    def test_invalid_json_response_returns_unsure(self):
        """Non-JSON model response -> all candidates become 'unsure'."""
        candidates = [_make_candidate(idx=i) for i in range(_PAIR_COUNT)]
        config = CuratorConfig(residue_to_agent=True)

        bad_llm = MagicMock()
        resp = MagicMock()
        resp.content = "This is not JSON"
        bad_llm.invoke.return_value = resp

        with (
            patch("curation.classifier.get_proxy_client"),
            patch("curation.classifier.ChatOpenAI", return_value=bad_llm),
        ):
            results = classify_residue(candidates, config)

        assert len(results) == len(candidates)
        for r in results:
            assert r.decision == "unsure"

    def test_partial_response_pads_with_unsure(self):
        """Model returns fewer decisions than candidates -> extras are 'unsure'."""
        candidates = [_make_candidate(idx=i) for i in range(_SMALL_COUNT)]
        config = CuratorConfig(residue_to_agent=True)

        short_llm = MagicMock()
        resp = MagicMock()
        resp.content = _make_decision_json(_SINGLE_COUNT)  # Only 1 decision for 3 candidates
        short_llm.invoke.return_value = resp

        with (
            patch("curation.classifier.get_proxy_client"),
            patch("curation.classifier.ChatOpenAI", return_value=short_llm),
        ):
            results = classify_residue(candidates, config)

        assert len(results) == len(candidates)
        assert results[0].decision == "include"
        assert results[1].decision == "unsure"
        assert results[2].decision == "unsure"

    def test_unknown_decision_value_normalized_to_unsure(self):
        """An unrecognised decision value is coerced to 'unsure'."""
        candidates = [_make_candidate(idx=0)]
        config = CuratorConfig(residue_to_agent=True)

        bad_decision_llm = MagicMock()
        resp = MagicMock()
        resp.content = json.dumps(
            [{"decision": "MAYBE", "doc_type": None, "module": None, "confidence": 0.5, "rationale": "dunno"}]
        )
        bad_decision_llm.invoke.return_value = resp

        with (
            patch("curation.classifier.get_proxy_client"),
            patch("curation.classifier.ChatOpenAI", return_value=bad_decision_llm),
        ):
            results = classify_residue(candidates, config)

        assert results[0].decision == "unsure"


class TestResultShape:
    def test_result_fields_populated(self, mock_llm_response):
        """All ClassificationResult fields are set correctly from the LLM response."""
        candidate = _make_candidate(idx=0)
        config = CuratorConfig(residue_to_agent=True)

        with (
            patch("curation.classifier.get_proxy_client"),
            patch("curation.classifier.ChatOpenAI", return_value=mock_llm_response),
        ):
            results = classify_residue([candidate], config)

        r = results[0]
        assert r.candidate is candidate
        assert r.decision == "include"
        assert r.doc_type == "tutorial"
        assert r.module == "eventing"
        assert r.confidence == pytest.approx(0.9)
        assert r.rationale == "user doc"
        assert r.decided_by == "agent"
