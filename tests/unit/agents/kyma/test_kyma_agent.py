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
