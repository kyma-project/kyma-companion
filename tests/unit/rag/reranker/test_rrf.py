import pytest
from langchain_core.documents import Document

from rag.reranker.rrf import get_relevant_documents
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


@pytest.mark.parametrize(
    "name, given_docs_list, given_limit, expected_docs_list",
    [
        (
            "given (empty documents), return empty list",
            [],
            10,
            [],
        ),
        (
            "given (duplicate documents and zero limit), return empty list",
            [
                [doc1, doc2, doc3],
                [doc1, doc2, doc3],
                [doc1, doc2, doc3],
            ],
            0,
            [],
        ),
        (
            "given (duplicate documents and negative limit), return all documents with highest relevance",
            [
                [doc1, doc2, doc3],
                [doc1, doc2, doc3],
                [doc1, doc2, doc3],
            ],
            -1,
            [doc1, doc2, doc3],
        ),
        (
            "given (duplicate documents and positive limit), return unique documents",
            [
                [doc1, doc2, doc3],
                [doc1, doc2, doc3],
                [doc1, doc2, doc3],
            ],
            10,
            [doc1, doc2, doc3],
        ),
        (
            "given (documents exceeding limit), return documents up to limit",
            [
                [doc1, doc2, doc3],
                [doc4, doc5, doc6],
                [doc7, doc8, doc9],
            ],
            4,
            [doc1, doc4, doc7, doc2],
        ),
        (
            "given (documents not exceeding limit), return documents up to limit",
            [
                [doc1, doc2, doc3],
                [doc4, doc5, doc6],
                [doc7, doc8, doc9],
            ],
            10,
            [doc1, doc4, doc7, doc2, doc5, doc8, doc3, doc6, doc9],
        ),
        (
            "given (documents with different positions in the list), return documents with highest relevance",
            [
                [doc1, doc2, doc3, doc6],
                [doc3, doc2, doc1, doc5],
                [doc3, doc2, doc4, doc1],
            ],
            10,
            [doc3, doc2, doc1, doc4, doc6, doc5],
        ),
    ],
)
def test_get_relevant_documents(
    name: str,
    given_docs_list: list[list[Document]],
    given_limit: int,
    expected_docs_list,
):
    # When
    actual_docs_list = get_relevant_documents(
        docs_list=given_docs_list, limit=given_limit
    )

    # Then
    assert actual_docs_list == expected_docs_list
    if given_limit >= 0:
        assert len(actual_docs_list) <= given_limit
