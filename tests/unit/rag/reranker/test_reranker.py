from unittest.mock import Mock

import pytest
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from rag.reranker.prompt import RERANKER_PROMPT_TEMPLATE
from rag.reranker.reranker import (
    LLMReranker,
    format_documents,
    format_queries,
    parse_response,
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
    doc_to_json,
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
        expected_chain = (
            prompt(RERANKER_PROMPT_TEMPLATE) | mock_model.llm | StrOutputParser()
        )

        # Then
        assert reranker is not None
        assert reranker.chain is not None
        assert reranker.chain == expected_chain

    def test_rerank(self):
        """
        Test the rerank method of the LLMReranker class.
        """

        # Given
        given_docs_list = [[doc1, doc4, doc7], [doc2, doc5, doc8], [doc3, doc6, doc9]]
        given_queries = ["this is a test query 1", "this is a test query 2"]
        given_input_limit = 10
        given_output_limit = 5
        expected_docs_list = [doc1, doc2, doc3, doc4, doc5]
        relevant_docs = [
            doc1,
            doc2,
            doc3,
            doc4,
            doc5,
            doc6,
            doc7,
            doc8,
            doc9,
        ]  # relevant documents after filtration

        mock_model = Mock()
        mock_model.name.return_value = "gpt-4o-mini"
        reranker = LLMReranker(model=mock_model)
        mock_response = format_json_block(*docs_to_json_str_list(expected_docs_list))
        reranker.chain = Mock()
        reranker.chain.invoke = Mock(return_value=mock_response)

        # When
        actual_docs_list = reranker.rerank(
            docs_list=given_docs_list,
            queries=given_queries,
            input_limit=given_input_limit,
            output_limit=given_output_limit,
        )

        # Then
        assert actual_docs_list == expected_docs_list
        reranker.chain.invoke.assert_called_once_with(
            {
                "documents": format_documents(relevant_docs),
                "queries": format_queries(given_queries),
                "limit": given_output_limit,
            }
        )


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


@pytest.mark.parametrize(
    "name, given_response, expected_docs",
    [
        (
            "given response is not surrounded by json code block",
            """
                [
                    {
                        "kwargs": {
                            "type": "Document",
                            "page_content": "this is a test content 1",
                            "metadata": {"type": "test 1", "metadata": "test 1"}
                        }
                    },
                    {
                        "kwargs": {
                            "type": "Document",
                            "page_content": "this is a test content 2",
                            "metadata": {"type": "test 2", "metadata": "test 2"}
                        }
                    }
                ]
                """,
            [
                Document(
                    type="Document",
                    page_content="this is a test content 1",
                ),
                Document(
                    type="Document",
                    page_content="this is a test content 2",
                ),
            ],
        ),
        (
            "given response is surrounded by json code block",
            """```json
                [
                    {
                        "kwargs": {
                            "type": "Document",
                            "page_content": "this is a test content 1",
                            "metadata": {"type": "test 1", "metadata": "test 1"}
                        }
                    },
                    {
                        "kwargs": {
                            "type": "Document",
                            "page_content": "this is a test content 2",
                            "metadata": {"type": "test 2", "metadata": "test 2"}
                        }
                    }
                ]
                ```""",
            [
                Document(
                    type="Document",
                    page_content="this is a test content 1",
                ),
                Document(
                    type="Document",
                    page_content="this is a test content 2",
                ),
            ],
        ),
    ],
)
def test_parse_response(name, given_response, expected_docs):
    # When
    actual_docs = parse_response(given_response)

    # Then
    assert actual_docs is not None
    assert len(actual_docs) == len(expected_docs)
    for i, doc in enumerate(actual_docs):
        assert doc == expected_docs[i]


def prompt(template: str) -> PromptTemplate:
    """
    Create a PromptTemplate object from the given template.
    :param template: A template string.
    :return: A PromptTemplate object.
    """
    return PromptTemplate.from_template(template)


def docs_to_json_str_list(docs: list[Document]) -> list[str]:
    """
    Convert a list of documents to a list of JSON strings.
    :param docs: A list of documents.
    :return: A list of JSON strings.
    """
    return [doc_to_json[doc.page_content] for doc in docs]


def format_json_block(*json_str: str) -> str:
    """
    Format the given json strings into a single json block.
    :param json_str: JSON strings to be formatted.
    :return: A single json block string containing the given json strings.
    """
    return "```json[{}]```".format(",".join(json_str))
