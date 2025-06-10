from unittest.mock import AsyncMock, Mock, patch

import pytest
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from rag.generator import Generator
from utils.models.factory import IModel


@pytest.fixture
def mock_model():
    """Create a mock model."""
    return Mock(spec=IModel)


@pytest.fixture
def mock_llm():
    """Create a mock LLM."""
    return Mock(spec=ChatOpenAI)


@pytest.fixture
def mock_chain():
    """Create a mock chain."""
    return AsyncMock()


class TestGenerator:
    """Test suite for Generator class."""

    def test_init(self, mock_model, mock_llm):
        """Test Generator initialization."""
        # Given
        mock_model.llm = mock_llm

        # When
        generator = Generator(mock_model)

        # Then
        assert generator.model == mock_model
        assert isinstance(generator.rag_chain.steps[0], PromptTemplate)
        assert generator.rag_chain.steps[1] == mock_llm
        assert isinstance(generator.rag_chain.steps[2], StrOutputParser)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "query, docs_content, expected_response, expected_error",
        [
            # Test case: Successful generation
            (
                "What is Kyma?",
                [
                    Document(page_content="Kyma is a cloud-native application runtime"),
                    Document(
                        page_content="It extends Kubernetes with serverless capabilities"
                    ),
                ],
                "Kyma is a cloud-native platform that extends Kubernetes",
                None,
            ),
            # Test case: Empty documents list
            (
                "What is Kyma?",
                [],
                "No relevant documentation found.",
                None,
            ),
            # Test case: Documents with only whitespace content
            (
                "What is Kyma?",
                [
                    Document(page_content="   "),
                    Document(page_content="\n\t  \n"),
                    Document(page_content=""),
                ],
                "No relevant documentation found.",
                None,
            ),
            # Test case: Documents with only empty strings
            (
                "What is Kyma?",
                [
                    Document(page_content=""),
                    Document(page_content=""),
                ],
                "No relevant documentation found.",
                None,
            ),
            # Test case: Error during generation
            (
                "What is Kyma?",
                [Document(page_content="Kyma content")],
                None,
                Exception("Error generating response"),
            ),
        ],
    )
    async def test_agenerate(
        self,
        mock_model,
        mock_chain,
        query,
        docs_content,
        expected_response,
        expected_error,
    ):
        """Test agenerate method including error logging and early return scenarios."""

        with patch("rag.generator.logger") as mock_logger:
            generator = Generator(mock_model)
            generator.rag_chain = mock_chain

            if expected_error:
                mock_chain.ainvoke.side_effect = expected_error
            else:
                mock_chain.ainvoke.return_value = expected_response

            if expected_error:
                with pytest.raises(Exception) as exc_info:
                    await generator.agenerate(docs_content, query)
                assert str(exc_info.value) == str(expected_error)
                mock_logger.exception.assert_called_once_with(
                    f"Error generating response for query: {query}"
                )
            else:
                result = await generator.agenerate(docs_content, query)
                assert result == expected_response
                mock_logger.exception.assert_not_called()

            docs_content_str = "\n\n".join(doc.page_content for doc in docs_content)

            if not docs_content_str.strip():
                # Early return case - chain should not be called
                mock_chain.ainvoke.assert_not_called()
            else:
                # Normal case - chain should be called with correct arguments
                mock_chain.ainvoke.assert_called_with(
                    config=None, input={"context": docs_content_str, "query": query}
                )
