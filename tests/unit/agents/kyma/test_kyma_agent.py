from dataclasses import dataclass
from unittest.mock import MagicMock, Mock, patch

import pytest
from langchain_core.embeddings import Embeddings

from agents.kyma.agent import KYMA_AGENT, KymaAgent
from agents.kyma.tools.query import fetch_kyma_resource_version, kyma_query_tool
from agents.kyma.tools.search import SearchKymaDocTool
from rag.system import RAGSystem
from utils.models.factory import IModel
from utils.settings import MAIN_EMBEDDING_MODEL_NAME, MAIN_MODEL_NAME


@pytest.fixture
def mock_models():
    gpt40 = MagicMock(spec=IModel)
    gpt40.name = MAIN_MODEL_NAME

    text_embedding_3_large = MagicMock(spec=Embeddings)
    text_embedding_3_large.name = "text-embedding-3-large"

    return {
        MAIN_MODEL_NAME: gpt40,
        MAIN_EMBEDDING_MODEL_NAME: text_embedding_3_large,
    }


@pytest.fixture
def doc_search_tool(mock_models):
    """Create a mock search tool."""
    # mock RAGSystem
    mock_rag_system = Mock(spec=RAGSystem)
    with patch("agents.kyma.tools.search.RAGSystem", return_value=mock_rag_system):
        tool = SearchKymaDocTool(mock_models)
        yield tool


def test_kyma_agent_init(mock_models, doc_search_tool):
    """Test that KymaAgent initializes correctly with all expected attributes."""
    agent = KymaAgent(mock_models)

    # Verify the agent name
    assert agent.name == KYMA_AGENT

    # Verify the model is set correctly
    assert agent.model == mock_models[MAIN_MODEL_NAME]

    # Verify the tools are set correctly
    expected_tools = [fetch_kyma_resource_version, kyma_query_tool, doc_search_tool]
    assert agent.tools == expected_tools


@dataclass
class MockDocument:
    page_content: str


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mock_documents,expected_output",
    [
        # Single document case
        ([MockDocument("Single document content")], "Single document content"),
        # Multiple documents case
        (
            [MockDocument("First doc"), MockDocument("Second doc")],
            "First doc\n\n -- next document -- \n\nSecond doc",
        ),
        # Three documents case
        (
            [MockDocument("Doc 1"), MockDocument("Doc 2"), MockDocument("Doc 3")],
            "Doc 1\n\n -- next document -- \n\nDoc 2\n\n -- next document -- \n\nDoc 3",
        ),
        # Empty documents list - should return fallback message
        ([], "No relevant documentation found."),
        # Documents with empty content
        ([MockDocument("")], "No relevant documentation found."),
        # Documents with only whitespace
        (
            [MockDocument("   "), MockDocument("\n\n")],
            "No relevant documentation found.",
        ),
        # Mixed content with special characters
        (
            [
                MockDocument("Content with special chars: !@#$"),
                MockDocument("Unicode: αβγ"),
            ],
            "Content with special chars: !@#$\n\n -- next document -- \n\nUnicode: αβγ",
        ),
        # Documents with newlines
        (
            [MockDocument("Multi\nline\ncontent"), MockDocument("Another\ndocument")],
            "Multi\nline\ncontent\n\n -- next document -- \n\nAnother\ndocument",
        ),
    ],
)
async def test_arun(mock_models, mock_documents, expected_output):
    """Test _arun method with different document scenarios"""

    mock_rag_system = Mock(spec=RAGSystem)
    with patch("agents.kyma.tools.search.RAGSystem", return_value=mock_rag_system):
        instance = SearchKymaDocTool(mock_models)
        instance.rag_system.aretrieve.return_value = mock_documents

        result = await instance._arun("test query")

        # Assert the output matches expected result
        assert result == expected_output

        # Verify aretrieve was called with correct Query object
        instance.rag_system.aretrieve.assert_called_once()
        called_query = instance.rag_system.aretrieve.call_args[0][0]
        assert called_query.text == "test query"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mock_documents,expected_output,top_k",
    [
        # Single document case with default top_k
        ([MockDocument("Single document content")], ["Single document content"], 4),
        # Multiple documents case
        (
            [MockDocument("First doc"), MockDocument("Second doc")],
            ["First doc", "Second doc"],
            4,
        ),
        # Three documents case
        (
            [MockDocument("Doc 1"), MockDocument("Doc 2"), MockDocument("Doc 3")],
            ["Doc 1", "Doc 2", "Doc 3"],
            4,
        ),
        # Empty documents list - should return empty list
        ([], [], 4),
        # Documents with empty content - should be filtered out
        ([MockDocument("")], [], 4),
        # Documents with only whitespace - should be filtered out
        ([MockDocument("   "), MockDocument("\n\n")], [], 4),
        # Mixed content: some empty, some with content
        (
            [
                MockDocument("Valid content"),
                MockDocument(""),
                MockDocument("Another valid"),
            ],
            ["Valid content", "Another valid"],
            4,
        ),
        # Documents with special characters
        (
            [
                MockDocument("Content with special chars: !@#$"),
                MockDocument("Unicode: αβγ"),
            ],
            ["Content with special chars: !@#$", "Unicode: αβγ"],
            4,
        ),
        # Documents with newlines
        (
            [MockDocument("Multi\nline\ncontent"), MockDocument("Another\ndocument")],
            ["Multi\nline\ncontent", "Another\ndocument"],
            4,
        ),
        # Mixed: whitespace and valid content
        (
            [MockDocument("   "), MockDocument("Valid"), MockDocument("\t\n")],
            ["Valid"],
            4,
        ),
        # Test with custom top_k=5
        (
            [MockDocument(f"Doc {i}") for i in range(5)],
            [f"Doc {i}" for i in range(5)],
            5,
        ),
        # Test with custom top_k=10
        (
            [MockDocument(f"Doc {i}") for i in range(10)],
            [f"Doc {i}" for i in range(10)],
            10,
        ),
        # Test with minimum top_k=1
        ([MockDocument("Single doc")], ["Single doc"], 1),
    ],
)
async def test_arun_list(mock_models, mock_documents, expected_output, top_k):
    """Test arun_list method with different document scenarios and top_k values"""

    mock_rag_system = Mock(spec=RAGSystem)
    with patch("agents.kyma.tools.search.RAGSystem", return_value=mock_rag_system):
        instance = SearchKymaDocTool(mock_models, top_k=top_k)
        instance.rag_system.aretrieve.return_value = mock_documents

        result = await instance.arun_list("test query")

        # Assert the output matches expected result
        assert result == expected_output

        # Verify aretrieve was called with correct Query object and top_k
        instance.rag_system.aretrieve.assert_called_once()
        called_query = instance.rag_system.aretrieve.call_args[0][0]
        assert called_query.text == "test query"
        call_kwargs = instance.rag_system.aretrieve.call_args[1]
        assert call_kwargs["top_k"] == top_k
