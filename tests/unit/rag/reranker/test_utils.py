from langchain_core.documents import Document

from rag.reranker.utils import dict_to_document, document_to_str, str_to_document


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
