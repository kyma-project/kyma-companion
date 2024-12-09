from unittest.mock import AsyncMock, Mock, patch

import pytest
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from rag.prompts import QUERY_GENERATOR_PROMPT_STRUCTURED_OUTPUT_TEMPLATE
from rag.query_generator import Queries, QueryGenerator
from utils.models.factory import IModel


@pytest.fixture
def mock_model():
    """Create a mock model."""
    return Mock(spec=IModel)


@pytest.fixture
def mock_llm():
    """Create a mock LLM."""
    return Mock(spec=ChatOpenAI)


class TestQueryGenerator:
    """Test suite for QueryGenerator class."""

    def test_init(self, mock_model):
        """Test QueryGenerator initialization."""
        # Given
        num_queries = 4
        prompt = ChatPromptTemplate.from_messages([("system", "test prompt")])

        # When
        generator = QueryGenerator(mock_model, prompt=prompt, num_queries=num_queries)

        # Then
        assert generator.model == mock_model
        assert generator.prompt == prompt
        assert generator._chain is not None

    def test_init_default_prompt(self, mock_model):
        """Test QueryGenerator initialization with default prompt."""
        # When
        generator = QueryGenerator(mock_model)

        # Then
        chain_steps_number = 3  # PromptTemplate | Model | OutputParser
        assert len(generator.prompt.messages) == chain_steps_number
        assert (
            generator.prompt.messages[0].prompt.template
            == QUERY_GENERATOR_PROMPT_STRUCTURED_OUTPUT_TEMPLATE
        )
        assert generator.prompt.messages[1].prompt.template == "Original query: {query}"

    def test_create_chain(self, mock_model, mock_llm):
        """Test _create_chain method."""
        # Given
        generator = QueryGenerator(mock_model)
        mock_model.llm = mock_llm

        # When
        chain = generator._create_chain()

        # Then
        assert chain is not None
        # Verify chain composition
        chain_steps_number = 2  # PromptTemplate | Model.with_structured_output()
        assert len(chain.steps) == chain_steps_number
        assert isinstance(chain.steps[0], ChatPromptTemplate)

    @pytest.mark.parametrize(
        "query, chain_output, expected_output, expected_error",
        [
            (
                "What is Kyma?",
                Queries(queries=["What is Kyma?", "Explain Kyma", "Define Kyma"]),
                Queries(queries=["What is Kyma?", "Explain Kyma", "Define Kyma"]),
                None,
            ),
            (
                "How to deploy function?",
                None,
                None,
                Exception("Error generating queries"),
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_agenerate_queries(
        self, mock_model, mock_llm, query, chain_output, expected_output, expected_error
    ):
        """Test agenerate_queries method."""
        mock_chain = AsyncMock()
        with patch.object(QueryGenerator, "_create_chain", return_value=mock_chain):
            generator = QueryGenerator(mock_model)
            # When/Then
            if expected_error:
                mock_chain.ainvoke.side_effect = expected_error

                with pytest.raises(type(expected_error)) as exc_info:
                    await generator.agenerate_queries(query)
                assert str(exc_info.value) == str(expected_error)
            else:
                mock_chain.ainvoke.return_value = chain_output

                result = await generator.agenerate_queries(query)
                assert result == expected_output
                mock_chain.ainvoke.assert_called_once_with({"query": query})
