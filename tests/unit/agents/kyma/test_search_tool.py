"""Unit tests for SearchKymaDocTool._arun formatting and arun_documents."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from agents.kyma.tools.search import SearchKymaDocTool, _format_document
from rag.system import RAGSystem
from utils.models.factory import IModel
from utils.settings import MAIN_EMBEDDING_MODEL_NAME, MAIN_MODEL_NAME


@pytest.fixture()
def mock_models() -> dict:
    """Minimal mock models dict."""
    model = Mock(spec=IModel)
    embedding = Mock(spec=Embeddings)
    return {MAIN_MODEL_NAME: model, MAIN_EMBEDDING_MODEL_NAME: embedding}


def _make_tool(mock_models: dict, docs: list[Document]) -> SearchKymaDocTool:
    """Create a SearchKymaDocTool with a mocked RAGSystem returning the given docs."""
    mock_rag = Mock(spec=RAGSystem)
    mock_rag.aretrieve = AsyncMock(return_value=docs)
    with patch("agents.kyma.tools.search.RAGSystem", return_value=mock_rag):
        tool = SearchKymaDocTool(mock_models)
    return tool


class TestFormatDocument:
    """Tests for the _format_document helper."""

    def test_format_with_title_and_url(self) -> None:
        """Formatted block contains title line, Source line, and content."""
        doc = Document(
            page_content="Some content here.",
            metadata={"title": "Kyma Functions", "url": "https://kyma.io/docs/functions"},
        )
        result = _format_document(doc)
        assert result.startswith("### Kyma Functions\n")
        assert "Source: https://kyma.io/docs/functions\n" in result
        assert "Some content here." in result

    def test_format_with_url_fallback_to_source(self) -> None:
        """Uses metadata.source when metadata.url is absent."""
        doc = Document(
            page_content="Content.",
            metadata={"title": "Doc", "source": "https://example.com/doc"},
        )
        result = _format_document(doc)
        assert "Source: https://example.com/doc" in result

    def test_format_without_url_omits_source_line(self) -> None:
        """No Source line when neither url nor source is present."""
        doc = Document(
            page_content="Content.",
            metadata={"title": "Doc"},
        )
        result = _format_document(doc)
        assert "Source:" not in result

    def test_format_without_title_uses_untitled(self) -> None:
        """Falls back to 'Untitled' when metadata.title is absent."""
        doc = Document(
            page_content="Content.",
            metadata={"url": "https://kyma.io"},
        )
        result = _format_document(doc)
        assert result.startswith("### Untitled\n")

    def test_format_with_module(self) -> None:
        """Module line is included when metadata.module is set."""
        doc = Document(
            page_content="Content.",
            metadata={"title": "API Rule", "url": "https://kyma.io", "module": "api-gateway"},
        )
        result = _format_document(doc)
        assert "Module: api-gateway\n" in result

    def test_format_without_module_omits_module_line(self) -> None:
        """No Module line when metadata.module is absent."""
        doc = Document(
            page_content="Content.",
            metadata={"title": "API Rule", "url": "https://kyma.io"},
        )
        result = _format_document(doc)
        assert "Module:" not in result


class TestSearchKymaDocToolArun:
    """Tests for SearchKymaDocTool._arun output format."""

    @pytest.mark.asyncio
    async def test_arun_formats_documents_with_title_and_url(self, mock_models: dict) -> None:
        """_arun returns formatted blocks joined by horizontal rules."""
        docs = [
            Document(
                page_content="First doc content.",
                metadata={"title": "First Doc", "url": "https://kyma.io/first"},
            ),
            Document(
                page_content="Second doc content.",
                metadata={"title": "Second Doc", "url": "https://kyma.io/second"},
            ),
        ]
        tool = _make_tool(mock_models, docs)
        result = await tool._arun("some query")

        assert "### First Doc" in result
        assert "Source: https://kyma.io/first" in result
        assert "First doc content." in result
        assert "### Second Doc" in result
        assert "Source: https://kyma.io/second" in result
        assert "---" in result

    @pytest.mark.asyncio
    async def test_arun_with_no_url_in_metadata(self, mock_models: dict) -> None:
        """_arun includes title even when url metadata is missing."""
        docs = [
            Document(
                page_content="Content without url.",
                metadata={"title": "My Doc"},
            ),
        ]
        tool = _make_tool(mock_models, docs)
        result = await tool._arun("query")

        assert "### My Doc" in result
        assert "Source:" not in result
        assert "Content without url." in result

    @pytest.mark.asyncio
    async def test_arun_no_results_returns_no_relevant_message(self, mock_models: dict) -> None:
        """_arun returns the not-found message when no docs are returned."""
        tool = _make_tool(mock_models, [])
        result = await tool._arun("query")
        assert result == "No relevant documentation found."

    @pytest.mark.asyncio
    async def test_arun_filters_empty_content(self, mock_models: dict) -> None:
        """_arun skips docs with empty or whitespace-only page_content."""
        docs = [
            Document(page_content="   ", metadata={}),
            Document(page_content="Good content.", metadata={"title": "Good"}),
        ]
        tool = _make_tool(mock_models, docs)
        result = await tool._arun("query")

        assert "Good content." in result
        # Only one block -- no separator needed
        assert result.count("---") == 0


class TestSearchKymaDocToolArunList:
    """Tests for backward-compatible arun_list method."""

    @pytest.mark.asyncio
    async def test_arun_list_returns_content_strings(self, mock_models: dict) -> None:
        """arun_list returns plain page_content strings (backward compat)."""
        docs = [
            Document(page_content="Doc A.", metadata={"title": "A", "url": "https://a.com"}),
            Document(page_content="Doc B.", metadata={"title": "B"}),
        ]
        tool = _make_tool(mock_models, docs)
        result = await tool.arun_list("query")
        assert result == ["Doc A.", "Doc B."]
