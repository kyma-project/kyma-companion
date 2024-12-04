from unittest.mock import Mock

from langchain_core.documents import Document
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate

from rag.reranker.prompt import RERANKER_PROMPT_TEMPLATE
from rag.reranker.reranker import (
    LLMReranker,
    RerankedDocs,
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

        reranked_docs_parser = PydanticOutputParser(pydantic_object=RerankedDocs)
        prompt = PromptTemplate.from_template(RERANKER_PROMPT_TEMPLATE).partial(
            format_instructions=reranked_docs_parser.get_format_instructions()
        )
        expected_chain = prompt | mock_model.llm | reranked_docs_parser

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
        mock_response = docs_to_reranked_docs(expected_docs_list)
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


def docs_to_reranked_docs(docs: list[Document]) -> RerankedDocs:
    """
    Convert a list of documents to a RerankedDocs object.
    :param docs: A list of documents.
    :return: A RerankedDocs object.
    """
    reranked_docs = RerankedDocs(documents=[])
    for doc in docs:
        reranked_docs.documents.append(doc)
    return reranked_docs
