"""Integration tests for the _tool_summarizer helper in react_agent.py.

Tests validate:
1. Short responses are returned unchanged (below token limit).
2. Large responses are summarized via ToolResponseSummarizer with real LLM calls.
3. Summarization produces relevant, faithful content.
4. Fallback to plain text when summarizer raises an exception.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest
from deepeval import assert_test
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from langchain_core.runnables import RunnableConfig

from agents.common.chunk_summarizer import ToolResponseSummarizer
from agents.common.utils import compute_string_token_count, convert_string_to_object
from agents.kyma.react_agent import CHUNK_LIMIT_EXCEEDED_RESPONSE, _tool_summarizer
from integration.agents.fixtures.k8_query_tool_response import (
    sample_deployment_tool_response,
    sample_pods_tool_response,
    sample_services_tool_response,
)
from utils.settings import (
    MAIN_MODEL_MINI_NAME,
    MAIN_MODEL_NAME,
    TOOL_RESPONSE_TOKEN_COUNT_LIMIT,
    TOTAL_CHUNKS_LIMIT,
)

# ---------------------------------------------------------------------------
# Test Case Dataclass
# ---------------------------------------------------------------------------


@dataclass
class ToolSummarizerTestCase:
    """Test case for _tool_summarizer integration testing."""

    name: str
    tool_response_raw: str  # raw string from fixture (JSON list)
    query: str
    token_limit: int  # override limit for the test
    expect_summarized: bool  # True if we expect summarization to occur
    expected_content_keywords: list[str]  # keywords that should appear in output


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def summarizer(app_models) -> ToolResponseSummarizer:
    """Create a real ToolResponseSummarizer backed by the mini model."""
    mini_model = app_models[MAIN_MODEL_MINI_NAME]
    return ToolResponseSummarizer(model=mini_model)


@pytest.fixture
def config() -> RunnableConfig:
    """Default runnable config for tests."""
    return RunnableConfig()


@pytest.fixture
def summarization_quality_metric(evaluator_model):
    """GEval metric for summarization quality."""
    return GEval(
        name="Summarization Quality",
        model=evaluator_model,
        threshold=0.6,
        evaluation_steps=[
            "Check whether the summary retains all critical information from the expected output.",
            "Verify the summary is relevant to the user query.",
            "Additional information is acceptable as long as it does not contradict the expected output.",
            "Penalize summaries that omit key facts relevant to the user query.",
        ],
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
    )


# ---------------------------------------------------------------------------
# 1. Short responses returned unchanged (below token limit)
# ---------------------------------------------------------------------------


class TestBelowTokenLimit:
    """Verify that responses under the token limit are returned as-is."""

    @pytest.mark.asyncio
    async def test_short_text_returned_unchanged(self, summarizer, config):
        """A short text should be returned verbatim without summarization."""
        short_text = "Pod nginx-abc123 is Running with 0 restarts."
        response = [{"status": "Running", "name": "nginx-abc123"}]

        result = await _tool_summarizer(
            response=response,
            text=short_text,
            query="What is the pod status?",
            summarizer=summarizer,
            config=config,
            token_limit=TOOL_RESPONSE_TOKEN_COUNT_LIMIT,
        )

        assert result == short_text

    @pytest.mark.asyncio
    async def test_empty_text_returned_unchanged(self, summarizer, config):
        """Empty string should be returned without error."""
        result = await _tool_summarizer(
            response=[],
            text="",
            query="list pods",
            summarizer=summarizer,
            config=config,
            token_limit=TOOL_RESPONSE_TOKEN_COUNT_LIMIT,
        )

        assert result == ""

    @pytest.mark.asyncio
    async def test_text_exactly_at_limit_returned_unchanged(self, summarizer, config):
        """Text exactly at the token limit should NOT be summarized (<=)."""
        # Build a text whose token count equals the limit
        base = "word "
        # compute token count of a single repetition to calibrate
        single_token_count = compute_string_token_count(base, MAIN_MODEL_NAME)
        # We want total token count == some small limit for the test
        small_limit = 50
        repetitions = small_limit // single_token_count
        text = base * repetitions
        # Verify we're at or under the limit
        actual_tokens = compute_string_token_count(text, MAIN_MODEL_NAME)

        result = await _tool_summarizer(
            response=[{"data": text}],
            text=text,
            query="What is this?",
            summarizer=summarizer,
            config=config,
            token_limit=actual_tokens,  # Set limit exactly to text size
        )

        assert result == text


# ---------------------------------------------------------------------------
# 2. Large responses are summarized (above token limit)
# ---------------------------------------------------------------------------

# NOTE: token_limit must be chosen so that num_chunks = (token_count // token_limit) + 1
# stays within TOTAL_CHUNKS_LIMIT. For these fixtures (~3.4k-5.5k tokens) a limit of
# 3000 forces summarization while keeping num_chunks == 2 (the default TOTAL_CHUNKS_LIMIT).
SUMMARIZATION_TOKEN_LIMIT = 3000

SUMMARIZATION_TEST_CASES = [
    ToolSummarizerTestCase(
        name="Large pods response is summarized with pod-related query",
        tool_response_raw=sample_pods_tool_response,
        query="List all pods in the cluster and their status",
        token_limit=SUMMARIZATION_TOKEN_LIMIT,  # forces summarization, num_chunks == 2
        expect_summarized=True,
        expected_content_keywords=["cert-manager", "Running"],
    ),
    ToolSummarizerTestCase(
        name="Large services response is summarized with service query",
        tool_response_raw=sample_services_tool_response,
        query="Which services are available in the cluster?",
        token_limit=SUMMARIZATION_TOKEN_LIMIT,
        expect_summarized=True,
        expected_content_keywords=["service", "istio"],
    ),
    ToolSummarizerTestCase(
        name="Large deployment response is summarized with health query",
        tool_response_raw=sample_deployment_tool_response,
        query="Are all deployments healthy?",
        token_limit=SUMMARIZATION_TOKEN_LIMIT,
        expect_summarized=True,
        expected_content_keywords=["cert-manager"],
    ),
]


@pytest.mark.parametrize(
    "test_case",
    SUMMARIZATION_TEST_CASES,
    ids=[tc.name for tc in SUMMARIZATION_TEST_CASES],
)
@pytest.mark.asyncio
async def test_large_response_is_summarized(
    summarizer,
    config,
    test_case: ToolSummarizerTestCase,
):
    """Verify that responses exceeding the token limit are summarized."""
    response_list = convert_string_to_object(test_case.tool_response_raw)
    text = test_case.tool_response_raw

    # Precondition: text exceeds our test token limit
    token_count = compute_string_token_count(text, MAIN_MODEL_NAME)
    assert token_count > test_case.token_limit, (
        f"Test setup error: text tokens ({token_count}) should exceed limit ({test_case.token_limit})"
    )

    result = await _tool_summarizer(
        response=response_list,
        text=text,
        query=test_case.query,
        summarizer=summarizer,
        config=config,
        token_limit=test_case.token_limit,
    )

    # Result should be shorter than original (summarization occurred)
    assert len(result) < len(text), (
        f"Expected summarized output to be shorter than original. "
        f"Original length: {len(text)}, Result length: {len(result)}"
    )

    # Result should be non-empty
    assert len(result) > 0, "Summarized result should not be empty"

    # Result should contain expected keywords (case-insensitive)
    result_lower = result.lower()
    for keyword in test_case.expected_content_keywords:
        assert keyword.lower() in result_lower, (
            f"Expected keyword '{keyword}' not found in summarized output: {result[:200]}..."
        )


# ---------------------------------------------------------------------------
# 3. Summarization quality evaluation (with LLM judge)
# ---------------------------------------------------------------------------


@dataclass
class SummarizationQualityTestCase:
    """Test case for evaluating summarization quality."""

    name: str
    tool_response_raw: str
    query: str
    expected_summary: str


QUALITY_TEST_CASES = [
    SummarizationQualityTestCase(
        name="Pod status summary captures key details",
        tool_response_raw=sample_pods_tool_response,
        query="List all pods and their status",
        expected_summary=(
            "Found 2 pods in cert-manager namespace: "
            "cert-manager-769fdd4544-tjwwk (Running, 63 restarts) and "
            "cert-manager-cainjector-56ccdfdd58-rsr4w (Running, 113 restarts)."
        ),
    ),
    SummarizationQualityTestCase(
        name="Deployment health summary is accurate",
        tool_response_raw=sample_deployment_tool_response,
        query="Are all deployments healthy?",
        expected_summary=(
            "Both cert-manager deployments are healthy with Available=True. "
            "cert-manager controller has 1/1 replicas available. "
            "cert-manager-cainjector has 1/1 replicas available."
        ),
    ),
    SummarizationQualityTestCase(
        name="Service summary captures external access info",
        tool_response_raw=sample_services_tool_response,
        query="Which services can be accessed from outside the cluster?",
        expected_summary=(
            "istio-ingressgateway is accessible externally as a LoadBalancer service "
            "with HTTP (port 80) and HTTPS (port 443) access."
        ),
    ),
]


@pytest.mark.parametrize(
    "test_case",
    QUALITY_TEST_CASES,
    ids=[tc.name for tc in QUALITY_TEST_CASES],
)
@pytest.mark.asyncio
async def test_summarization_quality(
    summarizer,
    config,
    summarization_quality_metric,
    test_case: SummarizationQualityTestCase,
):
    """Evaluate the quality of summarization output against expected summaries."""
    response_list = convert_string_to_object(test_case.tool_response_raw)
    text = test_case.tool_response_raw

    result = await _tool_summarizer(
        response=response_list,
        text=text,
        query=test_case.query,
        summarizer=summarizer,
        config=config,
        token_limit=SUMMARIZATION_TOKEN_LIMIT,  # forces summarization, num_chunks == 2
    )

    llm_test_case = LLMTestCase(
        input=f"User Query: {test_case.query}",
        actual_output=result,
        expected_output=test_case.expected_summary,
    )

    assert_test(llm_test_case, [summarization_quality_metric])


# ---------------------------------------------------------------------------
# 4. Fallback to plain text on summarization failure
# ---------------------------------------------------------------------------


class TestFallbackOnError:
    """Verify _tool_summarizer falls back to plain text when summarizer raises."""

    @pytest.mark.asyncio
    async def test_fallback_on_summarizer_exception(self, summarizer, config):
        """When summarizer raises, the original text should be returned."""
        original_text = "x " * 1000  # ~1001 tokens
        response_list = [{"data": original_text}]

        # token_limit=600 -> num_chunks = (1001//600)+1 = 2, within TOTAL_CHUNKS_LIMIT,
        # so the summarizer is actually invoked and its RuntimeError triggers the fallback.
        with patch.object(
            summarizer,
            "summarize_tool_response",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM service unavailable"),
        ):
            result = await _tool_summarizer(
                response=response_list,
                text=original_text,
                query="What is this?",
                summarizer=summarizer,
                config=config,
                token_limit=600,  # keeps num_chunks == 2
            )

        assert result == original_text

    @pytest.mark.asyncio
    async def test_fallback_on_timeout_exception(self, summarizer, config):
        """TimeoutError from summarizer should trigger fallback."""
        original_text = "pod data " * 500  # ~1001 tokens
        response_list = [{"pod": "data"}]

        with patch.object(
            summarizer,
            "summarize_tool_response",
            new_callable=AsyncMock,
            side_effect=TimeoutError("Request timed out"),
        ):
            result = await _tool_summarizer(
                response=response_list,
                text=original_text,
                query="pod status",
                summarizer=summarizer,
                config=config,
                token_limit=600,  # keeps num_chunks == 2
            )

        assert result == original_text

    @pytest.mark.asyncio
    async def test_fallback_on_value_error(self, summarizer, config):
        """ValueError from summarizer should trigger fallback."""
        original_text = "deployment info " * 300  # ~601 tokens
        response_list = [{"deployment": "info"}]

        with patch.object(
            summarizer,
            "summarize_tool_response",
            new_callable=AsyncMock,
            side_effect=ValueError("Invalid input to summarizer"),
        ):
            result = await _tool_summarizer(
                response=response_list,
                text=original_text,
                query="deployment health",
                summarizer=summarizer,
                config=config,
                token_limit=400,  # keeps num_chunks == 2
            )

        assert result == original_text


# ---------------------------------------------------------------------------
# 5. Config handling (None config)
# ---------------------------------------------------------------------------


class TestConfigHandling:
    """Verify _tool_summarizer handles None config correctly."""

    @pytest.mark.asyncio
    async def test_none_config_triggers_summarization(self, summarizer):
        """When config=None, summarization should still work (uses default RunnableConfig)."""
        response_list = convert_string_to_object(sample_pods_tool_response)
        text = sample_pods_tool_response

        result = await _tool_summarizer(
            response=response_list,
            text=text,
            query="List all pods",
            summarizer=summarizer,
            config=None,  # Explicitly pass None
            token_limit=SUMMARIZATION_TOKEN_LIMIT,
        )

        # Should still produce a summary (not crash)
        assert isinstance(result, str)
        assert len(result) > 0
        assert len(result) < len(text)

    @pytest.mark.asyncio
    async def test_none_config_short_text_unchanged(self, summarizer):
        """Short text with config=None should be returned unchanged."""
        short_text = "Everything is healthy."

        result = await _tool_summarizer(
            response=[],
            text=short_text,
            query="status check",
            summarizer=summarizer,
            config=None,
            token_limit=TOOL_RESPONSE_TOKEN_COUNT_LIMIT,
        )

        assert result == short_text


# ---------------------------------------------------------------------------
# 6. Query relevance in summarization
# ---------------------------------------------------------------------------


class TestQueryRelevance:
    """Verify that the summarization output is relevant to the provided query."""

    @pytest.mark.asyncio
    async def test_different_queries_produce_different_summaries(self, summarizer, config):
        """Same data with different queries should produce query-focused summaries."""
        response_list = convert_string_to_object(sample_pods_tool_response)
        text = sample_pods_tool_response

        # Query 1: focus on status
        result_status = await _tool_summarizer(
            response=response_list,
            text=text,
            query="What is the status of each pod?",
            summarizer=summarizer,
            config=config,
            token_limit=SUMMARIZATION_TOKEN_LIMIT,
        )

        # Query 2: focus on networking/IPs
        result_network = await _tool_summarizer(
            response=response_list,
            text=text,
            query="What are the IP addresses and networking details?",
            summarizer=summarizer,
            config=config,
            token_limit=SUMMARIZATION_TOKEN_LIMIT,
        )

        # Both should be non-empty summaries
        assert len(result_status) > 0
        assert len(result_network) > 0

        # They should be different (query-focused)
        assert result_status != result_network, "Different queries on the same data should produce different summaries"

    @pytest.mark.asyncio
    async def test_restart_focused_query_mentions_restarts(self, summarizer, config):
        """Query about restarts should produce summary mentioning restart counts."""
        response_list = convert_string_to_object(sample_pods_tool_response)
        text = sample_pods_tool_response

        result = await _tool_summarizer(
            response=response_list,
            text=text,
            query="Are there any pods with high restart counts or issues?",
            summarizer=summarizer,
            config=config,
            token_limit=SUMMARIZATION_TOKEN_LIMIT,
        )

        result_lower = result.lower()
        assert "restart" in result_lower, (
            f"Summary for restart-focused query should mention restarts. Got: {result[:300]}"
        )


# ---------------------------------------------------------------------------
# 7. Chunk limit enforcement (CHUNK_LIMIT_EXCEEDED_RESPONSE)
# ---------------------------------------------------------------------------


class TestChunkLimitExceeded:
    """Verify _tool_summarizer enforces TOTAL_CHUNKS_LIMIT.

    num_chunks = (token_count // token_limit) + 1. When this exceeds
    TOTAL_CHUNKS_LIMIT, the helper must return CHUNK_LIMIT_EXCEEDED_RESPONSE
    instead of falling back to the plain text.
    """

    @pytest.mark.asyncio
    async def test_returns_message_when_response_exceeds_chunk_limit(self, summarizer, config):
        """A large response with a small token_limit needs too many chunks and returns the limit message."""
        response_list = convert_string_to_object(sample_pods_tool_response)
        text = sample_pods_tool_response

        token_count = compute_string_token_count(text, MAIN_MODEL_NAME)
        small_limit = 50
        num_chunks = (token_count // small_limit) + 1
        # Sanity: this configuration must exceed the chunk limit.
        assert num_chunks > TOTAL_CHUNKS_LIMIT, (
            f"Test setup error: num_chunks ({num_chunks}) should exceed TOTAL_CHUNKS_LIMIT ({TOTAL_CHUNKS_LIMIT})"
        )

        result = await _tool_summarizer(
            response=response_list,
            text=text,
            query="List all pods",
            summarizer=summarizer,
            config=config,
            token_limit=small_limit,
        )
        assert result == CHUNK_LIMIT_EXCEEDED_RESPONSE

    @pytest.mark.asyncio
    async def test_summarizer_not_invoked_when_limit_exceeded(self, summarizer, config):
        """When the chunk limit is exceeded the summarizer LLM must NOT be called (fail fast)."""
        response_list = convert_string_to_object(sample_pods_tool_response)
        text = sample_pods_tool_response

        with patch.object(summarizer, "summarize_tool_response", new_callable=AsyncMock) as mock_summarize:
            result = await _tool_summarizer(
                response=response_list,
                text=text,
                query="List all pods",
                summarizer=summarizer,
                config=config,
                token_limit=50,
            )
            assert result == CHUNK_LIMIT_EXCEEDED_RESPONSE
            mock_summarize.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_chunk_limit_message_not_swallowed_by_fallback(self, summarizer, config):
        """The limit message must be returned, not the plain-text fallback.

        Even when the summarizer would raise a generic error, the chunk-limit check runs
        first, so the limit message is what surfaces.
        """
        response_list = convert_string_to_object(sample_pods_tool_response)
        text = sample_pods_tool_response

        with patch.object(
            summarizer,
            "summarize_tool_response",
            new_callable=AsyncMock,
            side_effect=RuntimeError("should not be reached"),
        ):
            result = await _tool_summarizer(
                response=response_list,
                text=text,
                query="List all pods",
                summarizer=summarizer,
                config=config,
                token_limit=50,
            )
            assert result == CHUNK_LIMIT_EXCEEDED_RESPONSE

    @pytest.mark.asyncio
    async def test_boundary_exactly_at_chunk_limit_succeeds(self, summarizer, config):
        """A response needing exactly TOTAL_CHUNKS_LIMIT chunks should summarize, not raise."""
        response_list = convert_string_to_object(sample_pods_tool_response)
        text = sample_pods_tool_response

        token_count = compute_string_token_count(text, MAIN_MODEL_NAME)
        # Pick a limit so num_chunks == TOTAL_CHUNKS_LIMIT and summarization is still triggered.
        # token_count / (TOTAL_CHUNKS_LIMIT - 0.5) yields token_count // limit == TOTAL_CHUNKS_LIMIT - 1.
        limit = int(token_count / (TOTAL_CHUNKS_LIMIT - 0.5))
        num_chunks = (token_count // limit) + 1
        assert num_chunks == TOTAL_CHUNKS_LIMIT, (
            f"Test setup error: expected num_chunks == {TOTAL_CHUNKS_LIMIT}, got {num_chunks}"
        )
        assert token_count > limit, "Test setup error: text must exceed limit to force summarization"

        result = await _tool_summarizer(
            response=response_list,
            text=text,
            query="List all pods",
            summarizer=summarizer,
            config=config,
            token_limit=limit,
        )

        assert isinstance(result, str)
        assert len(result) > 0
        assert len(result) < len(text)
