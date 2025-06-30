import pytest
from langchain_core.documents import Document

from rag.reranker.utils import (
    TMP_DOC_ID_PREFIX,
    dict_to_document,
    document_to_str,
    get_tmp_document_id,
    str_to_document,
)


@pytest.mark.parametrize(
    "identifier, prefix, expected",
    [
        ("abc", TMP_DOC_ID_PREFIX, "tmp-id-abc"),
        ("123", "custom-", "custom-123"),
        ("", TMP_DOC_ID_PREFIX, "tmp-id-"),
        ("xyz", "", "xyz"),
        ("test", None, "tmp-id-test"),
    ],
)
def test_get_tmp_document_id(identifier, prefix, expected):
    if prefix is None:
        assert get_tmp_document_id(identifier) == expected
    else:
        assert get_tmp_document_id(identifier, prefix) == expected


def test_document_to_str():
    # Given
    doc = Document(
        id="doc1",
        type="Document",
        page_content="this is a test content",
        metadata={"type": "test", "metadata": "test"},
    )

    # When
    s = document_to_str(doc)

    # Then
    assert s == '{"kwargs": {"id": "doc1", "page_content": "this is a test content"}}'


def test_dict_to_document():
    # Given
    obj = {
        "kwargs": {
            "type": "Document",
            "page_content": "this is a test content",
            "metadata": {"type": "test", "metadata": "test"},
        },
    }

    # When
    doc = dict_to_document(obj)

    # Then
    assert doc is not None
    assert doc.metadata == {}
    assert doc.type == "Document"
    assert doc.page_content == "this is a test content"


def test_str_to_document():
    # Given
    s = """
    {
        "kwargs": {
            "type": "Document",
            "page_content": "this is a test content",
            "metadata": {"type": "test", "metadata": "test"}
        }
    }
    """

    # When
    doc = str_to_document(s)

    # Then
    assert doc is not None
    assert doc.metadata == {}
    assert doc.type == "Document"
    assert doc.page_content == "this is a test content"
