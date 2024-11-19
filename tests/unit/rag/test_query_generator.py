from unittest.mock import Mock, patch

import pytest
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate

from rag.prompts import QUERY_GENERATOR_PROMPT_TEMPLATE
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
        assert isinstance(generator.queries_parser, PydanticOutputParser)
        assert generator._chain is not None

    def test_init_default_prompt(self, mock_model):
        """Test QueryGenerator initialization with default prompt."""
        # When
        generator = QueryGenerator(mock_model)

        # Then
        assert len(generator.prompt.messages) == 3
        assert (
            generator.prompt.messages[0].prompt.template
            == QUERY_GENERATOR_PROMPT_TEMPLATE
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
        assert len(chain.steps) == 3  # PromptTemplate | Model | OutputParser
        assert isinstance(chain.steps[0], ChatPromptTemplate)
        assert chain.steps[1] == mock_llm
        assert isinstance(chain.steps[2], PydanticOutputParser)

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
                Exception("Error invoking chain"),
            ),
        ],
    )
    def test_invoke_chain(
        self, mock_model, query, chain_output, expected_output, expected_error
    ):
        """Test _invoke_chain method."""
        # Given
        mock_chain = Mock()
        if expected_error:
            mock_chain.invoke = Mock(side_effect=expected_error)
        else:
            mock_chain.invoke = Mock(return_value=chain_output)

        with patch.object(QueryGenerator, "_create_chain", return_value=mock_chain):
            generator = QueryGenerator(mock_model)

            # When/Then
            if expected_error:
                with pytest.raises(type(expected_error)) as exc_info:
                    generator._invoke_chain(query)
                assert str(exc_info.value) == str(expected_error)
            else:
                result = generator._invoke_chain(query)
                assert result == expected_output
                mock_chain.invoke.assert_called_once_with({"query": query})

    @pytest.mark.parametrize(
        "query, expected_queries, expected_error",
        [
            (
                "What is Kyma?",
                Queries(queries=["What is Kyma?", "Explain Kyma", "Define Kyma"]),
                None,
            ),
            (
                "How to deploy function?",
                None,
                Exception("Error generating queries"),
            ),
        ],
    )
    def test_generate_queries(
        self, mock_model, mock_llm, query, expected_queries, expected_error
    ):
        """Test generate_queries method."""
        # Given
        mock_model.llm = mock_llm
        generator = QueryGenerator(mock_model)

        if expected_error:
            generator._invoke_chain = Mock(side_effect=expected_error)
        else:
            generator._invoke_chain = Mock(return_value=expected_queries)

        # When/Then
        if expected_error:
            with pytest.raises(type(expected_error)) as exc_info:
                generator.generate_queries(query)
            assert str(exc_info.value) == str(expected_error)
        else:
            result = generator.generate_queries(query)
            assert result == expected_queries
            generator._invoke_chain.assert_called_once_with(query)
