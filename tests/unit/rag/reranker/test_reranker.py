from unittest.mock import ANY, AsyncMock, Mock

import pytest
from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate

from rag.reranker.prompt import RERANKER_PROMPT_TEMPLATE
from rag.reranker.reranker import (
    DocumentRelevancyScores,
    LLMReranker,
    flatten_unique,
    format_documents,
    format_queries,
)
from unit.rag.reranker.fixtures import (
    doc1,
    doc2,
    doc3,
    doc4,
    doc5,
    doc6,
    doc7,
    doc8,
    doc9,
)


class TestLLMReranker:
    """
    Test class for the LLMReranker class.
    """

    def test_init(self):
        """
        Test the initialization of the LLMReranker class.
        """

        # Given
        mock_model = Mock()
        mock_model.name.return_value = "gpt-4o-mini"

        # When
        reranker = LLMReranker(model=mock_model)

        prompt = PromptTemplate.from_template(RERANKER_PROMPT_TEMPLATE)
        expected_chain = prompt | mock_model.llm.with_structured_output(
            DocumentRelevancyScores
        )

        # Then
        assert reranker is not None
        assert reranker.chain is not None
        assert reranker.chain == expected_chain

    @pytest.mark.parametrize(
        "name,"
        "given_docs_list,"
        "given_queries,"
        "given_input_limit,"
        "given_output_limit,"
        "given_relevant_docs,"  # documents that are used as an input to the LLM reranker.
        "given_raise_exception,"
        "expected_docs_list",
        [
            (
                "given (duplicate documents and exception raised) return unique relevant documents",
                [
                    # duplicate documents
                    [doc1, doc4, doc7],
                    [doc1, doc4, doc7],
                    [doc1, doc4, doc7],
                    # duplicate documents
                    [doc2, doc5, doc8],
                    [doc2, doc5, doc8],
                    [doc2, doc5, doc8],
                    # duplicate documents
                    [doc3, doc6, doc9],
                    [doc3, doc6, doc9],
                    [doc3, doc6, doc9],
                ],
                ["this is a test query 1", "this is a test query 2"],
                10,
                5,
                [doc1, doc2, doc3, doc4, doc5, doc6, doc7, doc8],
                True,
                [doc1, doc2, doc3, doc4, doc5],
            ),
            (
                "given (duplicate documents and exception not raised) return unique relevant documents",
                [
                    # duplicate documents
                    [doc1, doc4, doc7],
                    [doc1, doc4, doc7],
                    [doc1, doc4, doc7],
                    # duplicate documents
                    [doc2, doc5, doc8],
                    [doc2, doc5, doc8],
                    [doc2, doc5, doc8],
                    # duplicate documents
                    [doc3, doc6, doc9],
                    [doc3, doc6, doc9],
                    [doc3, doc6, doc9],
                ],
                ["this is a test query 1", "this is a test query 2"],
                10,
                5,
                [doc1, doc2, doc3, doc4, doc5, doc6, doc7, doc8],
                False,
                [doc1, doc2, doc3, doc4, doc5],
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_arerank(
        self,
        name: str,
        given_docs_list: list[list[Document]],
        given_queries: list[str],
        given_input_limit: int,
        given_output_limit: int,
        given_relevant_docs: list[Document],
        given_raise_exception: bool,
        expected_docs_list: list[Document],
    ):
        """
        Test the arerank method of the LLMReranker class.
        """

        # Given
        mock_response = expected_docs_list
        mock_model = Mock()
        mock_model.name.return_value = "gpt-4o-mini"
        reranker = LLMReranker(model=mock_model)
        reranker.chain = AsyncMock()
        reranker.chain.ainvoke.return_value.documents = mock_response
        if given_raise_exception:
            reranker.chain.ainvoke.side_effect = Exception("Some error occurred.")

        # When
        actual_docs_list = await reranker.arerank(
            docs_list=given_docs_list,
            queries=given_queries,
            input_limit=given_input_limit,
            output_limit=given_output_limit,
        )

        # Then
        assert actual_docs_list == expected_docs_list
        reranker.chain.ainvoke.assert_called_with(
            config=None,
            input={
                "documents": ANY,
                "queries": format_queries(given_queries),
                "limit": given_output_limit,
            },
        )


@pytest.mark.parametrize(
    "name, given_docs_list, given_limit, expected_docs",
    [
        (
            "given (empty documents), return empty list",
            [],
            10,
            [],
        ),
        (
            "given (one document), return list with one document",
            [
                [doc1],
            ],
            10,
            [doc1],
        ),
        (
            "given (same order duplicate documents and zero limit), return empty documents",
            [
                [doc1, doc2, doc3, doc4, doc5, doc6, doc7, doc8, doc9],
                [doc1, doc2, doc3, doc4, doc5, doc6, doc7, doc8, doc9],
                [doc1, doc2, doc3, doc4, doc5, doc6, doc7, doc8, doc9],
            ],
            0,
            [],
        ),
        (
            "given (same order duplicate documents and negative limit), return all unique documents",
            [
                [doc1, doc2, doc3, doc4, doc5, doc6, doc7, doc8, doc9],
                [doc1, doc2, doc3, doc4, doc5, doc6, doc7, doc8, doc9],
                [doc1, doc2, doc3, doc4, doc5, doc6, doc7, doc8, doc9],
            ],
            -1,
            [doc1, doc2, doc3, doc4, doc5, doc6, doc7, doc8, doc9],
        ),
        (
            "given (same order duplicate documents and positive limit), return unique documents up to limit",
            [
                [doc1, doc2, doc3, doc4, doc5, doc6, doc7, doc8, doc9],
                [doc1, doc2, doc3, doc4, doc5, doc6, doc7, doc8, doc9],
                [doc1, doc2, doc3, doc4, doc5, doc6, doc7, doc8, doc9],
            ],
            3,
            [doc1, doc2, doc3],
        ),
        (
            "given (unordered duplicate documents and positive limit),"
            "return unique documents up to limit in order of first occurrence",
            [
                [doc9, doc8, doc7, doc6, doc5, doc4, doc3, doc2, doc1],
                [doc1, doc2, doc3, doc4, doc5, doc6, doc7, doc8, doc9],
                [doc1, doc2, doc3, doc4, doc5, doc6, doc7, doc8, doc9],
            ],
            3,
            [doc9, doc8, doc7],
        ),
    ],
)
def test_flatten_unique(
    name: str,
    given_docs_list: list[list[Document]],
    given_limit: int,
    expected_docs: list[Document],
):
    # When
    actual_docs = flatten_unique(given_docs_list, given_limit)

    # Then
    assert actual_docs == expected_docs


def test_format_documents():
    # Given
    docs = [
        Document(
            type="Document",
            page_content="this is a test content 1",
            metadata={"type": "test 1", "metadata": "test 1"},
        ),
        Document(
            type="Document",
            page_content="this is a test content 2",
            metadata={"type": "test 2", "metadata": "test 2"},
        ),
    ]

    # When
    s = format_documents(docs)

    # Then
    assert s == (
        '[{"kwargs": {"page_content": "this is a test content 1"}},'
        '{"kwargs": {"page_content": "this is a test content 2"}}]'
    )


def test_format_queries():
    # Given
    queries = ["this is a test query 1", "this is a test query 2"]

    # When
    s = format_queries(queries)

    # Then
    assert s == '["this is a test query 1","this is a test query 2"]'
