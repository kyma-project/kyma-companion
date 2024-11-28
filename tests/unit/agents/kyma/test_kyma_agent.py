from unittest.mock import Mock, patch

import pytest
from langchain_core.embeddings import Embeddings

from agents.kyma.agent import KYMA_AGENT, KymaAgent
from agents.kyma.tools.query import kyma_query_tool
from agents.kyma.tools.search import SearchKymaDocTool
from rag.system import RAGSystem
from utils.models.factory import IModel, ModelType


@pytest.fixture
def mock_models():
    """Create mock models dictionary with required model types."""
    return {
        ModelType.GPT4O: Mock(spec=IModel),
        ModelType.TEXT_EMBEDDING_3_LARGE: Mock(spec=Embeddings),
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
    assert agent.model == mock_models[ModelType.GPT4O]

    # Verify the tools are set correctly
    expected_tools = [doc_search_tool, kyma_query_tool]
    assert agent.tools == expected_tools
