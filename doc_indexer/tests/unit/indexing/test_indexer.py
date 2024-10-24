from typing import List, Any
from unittest.mock import Mock, patch

import pytest
from langchain_core.documents import Document

from indexing.contants import HEADER1
from indexing.indexer import create_chunks, MarkdownIndexer


@pytest.fixture
def sample_documents() -> List[Document]:
    return [
        Document(
            page_content="""
            # Header
            Content 0""".strip()
        ),
        Document(
            page_content="""
            # Header 1
            Content 1
            ## Header 2
            Content 2
            # Header one
            Content 3""".strip()
        ),
        Document(
            page_content="""
            # Another Header
            Some content
            ## Subheader
            More content""".strip()
        ),
        Document(page_content="No headers here, just plain content."),
    ]


# Define test cases separately for better readability
NORMAL_TEST_CASES = [
    (
        "sample_documents",
        [("#", "Header 1")],
        [
            """# Header
            Content 0""".strip(),
            """# Header 1
            Content 1
            ## Header 2
            Content 2""".strip(),
            """# Header one
            Content 3""".strip(),
            """# Another Header
            Some content
            ## Subheader
            More content""".strip(),
            "No headers here, just plain content.",
        ],
        None,
    ),
    (
        "sample_documents",
        [("#", "Header 1"), ("##", "Header 2")],
        [
            """# Header
            Content 0""".strip(),
            """# Header 1
            Content 1""".strip(),
            """## Header 2
            Content 2""".strip(),
            """# Header one
            Content 3""".strip(),
            """# Another Header
            Some content""".strip(),
            """## Subheader
            More content""".strip(),
            "No headers here, just plain content.",
        ],
        None,
    ),
]

EDGE_CASES = [
    ([], [("#", "Header 1")], [], None),
    (
        [Document(page_content="No headers here, just plain content.")],
        [("#", "Header 1")],
        ["No headers here, just plain content."],
        None,
    ),
]

ERROR_CASES = [
    (None, [("#", "Header 1")], None, TypeError),
    ("Not a list", [("#", "Header 1")], None, AttributeError),
    ([None], [("#", "Header 1")], None, AttributeError),
    ([{"not": "a document"}], [("#", "Header 1")], None, AttributeError),
]


@pytest.mark.parametrize(
    "input_docs, headers_to_split_on, expected_chunks, expected_exception",
    NORMAL_TEST_CASES + EDGE_CASES + ERROR_CASES,
)
def test_create_chunks(
    sample_documents: List[Document],
    input_docs: Any,
    headers_to_split_on: List[tuple],
    expected_chunks: List[str],
    expected_exception: type,
):
    if input_docs == "sample_documents":
        input_docs = sample_documents

    if expected_exception:
        with pytest.raises(expected_exception):
            create_chunks(input_docs, headers_to_split_on)
    else:
        result = create_chunks(input_docs, headers_to_split_on)
        assert len(result) == len(expected_chunks)
        for res, exp in zip(result, expected_chunks):
            assert res.page_content.strip() == exp.strip()


@pytest.fixture
def mock_embedding():
    return Mock()


@pytest.fixture
def mock_connection():
    return Mock()


@pytest.fixture
def mock_hana_db():
    with patch("indexing.indexer.HanaDB") as mock:
        yield mock


@pytest.fixture
def indexer(mock_embedding, mock_connection, mock_hana_db):
    return MarkdownIndexer(
        docs_path="",
        embedding=mock_embedding,
        connection=mock_connection,
        table_name="test_table",
    )


@pytest.mark.parametrize(
    "test_case,docs_path,expected_docs_number, expected_exception",
    [
        (
            "Multiple documents",
            "./unit/fixtures/test_docs",
            4,
            None,
        ),
        (
            "Double nested subdirectories",
            "./unit/fixtures/double_nested_dirs",
            2,
            None,
        ),
        (
            "No subdirectories",
            "./unit/fixtures/single_doc",
            1,
            None,
        ),
        (
            "Empty directory",
            "./unit/fixtures/empty_dir",
            0,
            None,
        ),
        (
            "Non-existent directory",
            "./unit/fixtures/non_existent_dir",
            0,
            FileNotFoundError,
        ),
    ],
)
def test_load_documents(
    indexer, test_case, docs_path, expected_docs_number, expected_exception
):
    indexer.docs_path = docs_path
    if expected_exception:
        with pytest.raises(expected_exception):
            indexer._load_documents()
    else:
        result = indexer._load_documents()
        assert len(result) == expected_docs_number, f"Failed case: {test_case}"


@pytest.mark.parametrize(
    "test_case,headers_to_split_on,loaded_docs,expected_chunks,delete_error,add_error,expected_exception",
    [
        (
            "Default header",
            None,
            [
                Document(
                    page_content="# My Header 1\nContent",
                )
            ],
            [
                Document(
                    page_content="# My second Header 1 \nContent",
                )
            ],
            None,
            None,
            None,
        ),
        (
            "Custom headers",
            [("##", "Header2")],
            [
                Document(
                    page_content="# H1\n## H2\nContent",
                )
            ],
            [
                Document(
                    page_content="# H1\n", metadata={"source": "/test/docs/file1.md"}
                ),
                Document(
                    page_content="## H2\nContent",
                ),
            ],
            None,
            None,
            None,
        ),
        (
            "Delete error",
            None,
            [],
            [],
            Exception("Delete error"),
            None,
            Exception,
        ),
        (
            "Add documents error",
            None,
            [],
            [],
            None,
            Exception("Add documents error"),
            Exception,
        ),
    ],
)
def test_index(
    indexer,
    mock_hana_db,
    test_case,
    headers_to_split_on,
    loaded_docs,
    expected_chunks,
    delete_error,
    add_error,
    expected_exception,
):
    indexer.db.delete.side_effect = delete_error
    indexer.db.add_documents.side_effect = add_error

    with patch.object(indexer, "_load_documents", return_value=loaded_docs):
        with patch(
            "indexing.indexer.create_chunks", return_value=expected_chunks
        ) as mock_create_chunks:
            if expected_exception:
                with pytest.raises(expected_exception):
                    indexer.index(headers_to_split_on)
            else:
                indexer.index(headers_to_split_on)

                mock_create_chunks.assert_called_once_with(
                    loaded_docs, headers_to_split_on or [HEADER1]
                )
                indexer.db.delete.assert_called_once_with(filter={})
                indexer.db.add_documents.assert_called_once_with(expected_chunks)

    if delete_error:
        assert str(delete_error) in str(indexer.db.delete.side_effect)
    if add_error:
        assert str(add_error) in str(indexer.db.add_documents.side_effect)
