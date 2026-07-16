"""Unit tests for ToolResponseSummarizer -- fully deterministic, no LLM credentials needed.

Covers three layers:
1. _create_chunks_from_list -- shape, ceil-division, item membership, empty-list edge case.
2. summarize_tool_response join logic -- FakeMessagesListChatModel, asserts join result.
3. End-to-end with the real deployment fixture -- FakeMessagesListChatModel returns a scripted
   summary that contains the verbatim values from the fixture; asserts those values survive.
"""

from unittest.mock import MagicMock

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from agents.common.chunk_summarizer import ToolResponseSummarizer
from agents.common.prompts import CHUNK_SUMMARIZER_PROMPT
from agents.common.utils import convert_string_to_object
from integration.agents.fixtures.k8_query_tool_response import sample_deployment_tool_response
from utils.models.factory import IModel


def _make_summarizer(fake_llm: FakeMessagesListChatModel) -> ToolResponseSummarizer:
    """Build a ToolResponseSummarizer backed by a scripted fake LLM.

    ToolResponseSummarizer._create_chain builds ``PromptTemplate | model.llm``.
    FakeMessagesListChatModel is a LangChain Runnable, so it can be assigned
    directly to model.llm without going through bind_tools.
    """
    mock_model = MagicMock(spec=IModel)
    mock_model.llm = fake_llm
    return ToolResponseSummarizer(mock_model)


def _make_summarizer_with_mock_llm() -> ToolResponseSummarizer:
    """Build a ToolResponseSummarizer with a plain mock LLM (for shape-only tests)."""
    mock_model = MagicMock(spec=IModel)
    mock_model.llm = MagicMock()
    return ToolResponseSummarizer(mock_model)


# ---------------------------------------------------------------------------
# Prompt sanity check (module-level -- no summarizer needed)
# ---------------------------------------------------------------------------


def test_prompt_template_contains_required_variables() -> None:
    """The chain prompt must expose 'query' and 'tool_response_chunk' variables."""
    assert "query" in CHUNK_SUMMARIZER_PROMPT
    assert "tool_response_chunk" in CHUNK_SUMMARIZER_PROMPT


# ---------------------------------------------------------------------------
# 1. _create_chunks_from_list
# ---------------------------------------------------------------------------


class TestCreateChunksFromList:
    @pytest.fixture
    def summarizer(self) -> ToolResponseSummarizer:
        return _make_summarizer_with_mock_llm()

    def test_exact_division_produces_correct_chunk_count(self, summarizer: ToolResponseSummarizer) -> None:
        """4 items / 2 chunks -> 2 chunks of 2 items each."""
        items = ["a", "b", "c", "d"]
        chunks = summarizer._create_chunks_from_list(items, nums_of_chunks=2)
        assert len(chunks) == 2

    def test_exact_division_chunk_sizes(self, summarizer: ToolResponseSummarizer) -> None:
        items = ["a", "b", "c", "d"]
        chunks = summarizer._create_chunks_from_list(items, nums_of_chunks=2)
        assert chunks[0].page_content == "a\n\nb"
        assert chunks[1].page_content == "c\n\nd"

    def test_inexact_division_last_chunk_is_smaller(self, summarizer: ToolResponseSummarizer) -> None:
        """3 items / 2 chunks -> ceil(3/2)=2 -> first chunk has 2, second has 1."""
        items = ["x", "y", "z"]
        chunks = summarizer._create_chunks_from_list(items, nums_of_chunks=2)
        assert len(chunks) == 2
        assert chunks[0].page_content == "x\n\ny"
        assert chunks[1].page_content == "z"

    def test_single_item_list(self, summarizer: ToolResponseSummarizer) -> None:
        chunks = summarizer._create_chunks_from_list(["only"], nums_of_chunks=3)
        assert len(chunks) == 1
        assert chunks[0].page_content == "only"

    def test_empty_list_returns_empty(self, summarizer: ToolResponseSummarizer) -> None:
        chunks = summarizer._create_chunks_from_list([], nums_of_chunks=2)
        assert chunks == []

    def test_all_items_appear_in_exactly_one_chunk(self, summarizer: ToolResponseSummarizer) -> None:
        """No item is dropped or duplicated across chunks."""
        items = [str(i) for i in range(7)]
        chunks = summarizer._create_chunks_from_list(items, nums_of_chunks=3)
        all_content = "\n".join(c.page_content for c in chunks)
        for item in items:
            assert all_content.count(item) == 1, f"Item {item!r} appeared wrong number of times"


# ---------------------------------------------------------------------------
# 2. summarize_tool_response join logic
# ---------------------------------------------------------------------------


class TestSummarizeToolResponseJoin:
    @pytest.mark.asyncio
    async def test_two_chunk_summaries_are_joined_with_double_newline(self) -> None:
        """summarize_tool_response joins chunk summaries with '\\n\\n'."""
        fake_llm = FakeMessagesListChatModel(
            responses=[
                AIMessage(content="chunk-summary-1"),
                AIMessage(content="chunk-summary-2"),
            ]
        )
        summarizer = _make_summarizer(fake_llm)
        result = await summarizer.summarize_tool_response(
            tool_response=[{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}],
            user_query="any query",
            config={},
            nums_of_chunks=2,
        )
        assert result == "chunk-summary-1\n\nchunk-summary-2"

    @pytest.mark.asyncio
    async def test_single_chunk_returns_content_without_extra_newlines(self) -> None:
        fake_llm = FakeMessagesListChatModel(responses=[AIMessage(content="only-summary")])
        summarizer = _make_summarizer(fake_llm)
        result = await summarizer.summarize_tool_response(
            tool_response=[{"id": 1}],
            user_query="any query",
            config={},
            nums_of_chunks=1,
        )
        assert result == "only-summary"

    @pytest.mark.asyncio
    async def test_empty_tool_response_returns_empty_string(self) -> None:
        fake_llm = FakeMessagesListChatModel(responses=[])
        summarizer = _make_summarizer(fake_llm)
        result = await summarizer.summarize_tool_response(
            tool_response=[],
            user_query="any query",
            config={},
            nums_of_chunks=2,
        )
        assert result == ""

    @pytest.mark.asyncio
    async def test_three_chunk_summaries_are_joined_in_order(self) -> None:
        fake_llm = FakeMessagesListChatModel(
            responses=[
                AIMessage(content="first"),
                AIMessage(content="second"),
                AIMessage(content="third"),
            ]
        )
        summarizer = _make_summarizer(fake_llm)
        result = await summarizer.summarize_tool_response(
            tool_response=list(range(6)),
            user_query="any query",
            config={},
            nums_of_chunks=3,
        )
        assert result == "first\n\nsecond\n\nthird"


# ---------------------------------------------------------------------------
# 3. End-to-end with the real deployment fixture (no live LLM)
# ---------------------------------------------------------------------------


class TestExposedPortsWithFakeLlm:
    """Covers the 'Should identify exposed ports from deployment' integration case.

    The deployment fixture contains:
    - containerPort 9402 with name 'http-metrics'
    - Prometheus annotations: prometheus.io/scrape=true, prometheus.io/port=9402

    We split it into 2 chunks (matching the integration test nums_of_chunks=2).
    The fake LLM returns a scripted summary that includes those values.
    Assertions verify the scripted summary is returned verbatim -- no LLM variance.
    """

    SCRIPTED_SUMMARY = (
        "cert-manager-controller exposes port 9402 (http-metrics) with TCP protocol. "
        "Prometheus annotations: prometheus.io/scrape=true, prometheus.io/port=9402, "
        "prometheus.io/path=/metrics."
    )

    @pytest.mark.asyncio
    async def test_exposed_ports_scripted_summary_contains_port_number(self) -> None:
        fake_llm = FakeMessagesListChatModel(
            responses=[
                AIMessage(content=self.SCRIPTED_SUMMARY),
                AIMessage(content="cert-manager-cainjector has no exposed ports."),
            ]
        )
        summarizer = _make_summarizer(fake_llm)
        tool_response_list = convert_string_to_object(sample_deployment_tool_response)

        result = await summarizer.summarize_tool_response(
            tool_response=tool_response_list,
            user_query="What ports are exposed by the deployment?",
            config={},
            nums_of_chunks=2,
        )

        assert "9402" in result
        assert "http-metrics" in result

    @pytest.mark.asyncio
    async def test_exposed_ports_scripted_summary_contains_prometheus_annotations(self) -> None:
        fake_llm = FakeMessagesListChatModel(
            responses=[
                AIMessage(content=self.SCRIPTED_SUMMARY),
                AIMessage(content="No additional ports."),
            ]
        )
        summarizer = _make_summarizer(fake_llm)
        tool_response_list = convert_string_to_object(sample_deployment_tool_response)

        result = await summarizer.summarize_tool_response(
            tool_response=tool_response_list,
            user_query="What ports are exposed by the deployment?",
            config={},
            nums_of_chunks=2,
        )

        assert "prometheus.io/scrape" in result
        assert "prometheus.io/port" in result

    def test_fixture_is_split_into_correct_chunk_count(self) -> None:
        """Verify the deployment fixture (2 items) splits into exactly 2 chunks at nums_of_chunks=2."""
        tool_response_list = convert_string_to_object(sample_deployment_tool_response)
        summarizer = _make_summarizer_with_mock_llm()

        chunks = summarizer._create_chunks_from_list(tool_response_list, nums_of_chunks=2)

        assert len(chunks) == 2
        # Each chunk must contain exactly one deployment object's data
        assert "cert-manager-controller" in chunks[0].page_content
        assert "cert-manager-cainjector" in chunks[1].page_content
