from typing import Any
from unittest.mock import Mock, call, patch

import pytest
from indexing.indexer import MarkdownIndexer, create_chunks
from langchain_core.documents import Document

SINGLE_BATCH_DOCS = [Document(page_content="# My Header 1\nContent")]
TABLE_NAME = "test_table"
BACKUP_TABLE_NAME = "backup_test_table"


@pytest.fixture(scope="session")
def fixtures_path(root_tests_path) -> str:
    return f"{root_tests_path}/unit/fixtures"


@pytest.fixture
def mock_embedding():
    return Mock()


@pytest.fixture
def mock_connection():
    return Mock()


@pytest.fixture
def mock_hana_db():
    with patch("indexing.indexer.HanaDB") as mock:
        mock_instance = mock.return_value
        mock_instance.close = patch("indexing.indexer.HanaDB.close").start()
        mock_instance.table_name = TABLE_NAME
        mock_instance.delete = Mock()
        yield mock


@pytest.fixture
def indexer(mock_embedding, mock_connection, mock_hana_db):
    indexer = MarkdownIndexer(
        docs_path="",
        embedding=mock_embedding,
        connection=mock_connection,
        table_name=TABLE_NAME,
        backup_table_name=BACKUP_TABLE_NAME,
    )
    return indexer


@pytest.fixture
def sample_documents() -> list[Document]:
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


@pytest.mark.parametrize(
    "input_docs, headers_to_split_on, expected_chunks, expected_exception",
    [
        (
            "sample_documents",
            [("#", "Header 1")],
            [
                "# Header\nContent 0".strip(),
                "# Header 1\nContent 1\n## Header 2\nContent 2",
                "# Header one\nContent 3",
                "# Another Header\nSome content\n## Subheader\nMore content",
                "No headers here, just plain content.",
            ],
            None,
        ),
        (
            "sample_documents",
            [("#", "Header 1"), ("##", "Header 2")],
            [
                "# Header\nContent 0",
                "# Header 1\nContent 1",
                "## Header 2\nContent 2",
                "# Header one\nContent 3",
                "# Another Header\nSome content",
                "## Subheader\nMore content",
                "No headers here, just plain content.",
            ],
            None,
        ),
        # Edge cases
        ([], [("#", "Header 1")], [], None),
        (
            [Document(page_content="No headers here, just plain content.")],
            [("#", "Header 1")],
            ["No headers here, just plain content."],
            None,
        ),
        # error cases
        (None, [("#", "Header 1")], None, TypeError),
        ("Not a list", [("#", "Header 1")], None, AttributeError),
        ([None], [("#", "Header 1")], None, AttributeError),
        ([{"not": "a document"}], [("#", "Header 1")], None, AttributeError),
    ],
)
def test_create_chunks(
    sample_documents: list[Document],
    input_docs: Any,
    headers_to_split_on: list[tuple],
    expected_chunks: list[str],
    expected_exception: type,
) -> None:
    if input_docs == "sample_documents":
        input_docs = sample_documents

    if expected_exception:
        with pytest.raises(expected_exception):
            create_chunks(input_docs, headers_to_split_on)
    else:
        result = create_chunks(input_docs, headers_to_split_on)
        assert len(result) == len(expected_chunks)
        for res, exp in zip(result, expected_chunks, strict=False):
            assert res.page_content.strip() == exp.strip()


@pytest.mark.parametrize(
    "test_case,docs_path,expected_docs_number, expected_exception",
    [
        (
            "Multiple documents",
            "./test_docs",
            4,
            None,
        ),
        (
            "Double nested subdirectories",
            "./double_nested_dirs",
            2,
            None,
        ),
        (
            "No subdirectories",
            "./single_doc",
            1,
            None,
        ),
        (
            "Empty directory",
            "./empty_dir",
            0,
            None,
        ),
        (
            "Non-existent directory",
            "./non_existent_dir",
            0,
            FileNotFoundError,
        ),
    ],
)
def test_load_documents(
    fixtures_path,
    indexer,
    test_case,
    docs_path,
    expected_docs_number,
    expected_exception,
) -> None:
    indexer.docs_path = fixtures_path + "/" + docs_path
    if expected_exception:
        with pytest.raises(expected_exception):
            indexer._load_documents()
    else:
        result = indexer._load_documents()
        assert len(result) == expected_docs_number, f"Failed case: {test_case}"


@pytest.mark.parametrize(
    "test_case,headers_to_split_on,loaded_docs,expected_chunks",
    [
        (
            "Single batch",
            None,
            SINGLE_BATCH_DOCS,
            SINGLE_BATCH_DOCS,
        ),
        (
            "Multiple batches",
            None,
            [Document(page_content=f"# Header {i}\nContent") for i in range(6)],  # Assuming CHUNKS_BATCH_SIZE is 5
            [Document(page_content=f"# Header {i}\nContent") for i in range(6)],
        ),
    ],
)
def test_index_batches(
    indexer,
    mock_hana_db,
    test_case,
    headers_to_split_on,
    loaded_docs,
    expected_chunks,
) -> None:
    with (
        patch.object(indexer, "_load_documents", return_value=loaded_docs),
        patch("indexing.indexer.create_chunks", return_value=expected_chunks) as mock_create_chunks,
        patch("indexing.indexer.CHUNKS_BATCH_SIZE", 5),
        patch("time.sleep") as mock_sleep,
        patch.object(indexer, "_copy_table") as mock_copy_table,
    ):
        # Given:
        indexer.headers_to_split_on = headers_to_split_on

        # When:
        indexer.index()

        # Then:
        # Verify that _load_documents was called.
        mock_create_chunks.assert_called_once_with(loaded_docs, headers_to_split_on)

        # Calculate the expected number of batches.
        num_chunks = len(expected_chunks)
        batch_size = 5  # from the mocked CHUNKS_BATCH_SIZE
        expected_batches = [expected_chunks[i : i + batch_size] for i in range(0, num_chunks, batch_size)]

        # Verify that add_documents was called for each batch.
        assert indexer.db.add_documents.call_count == len(expected_batches)
        for i, batch in enumerate(expected_batches):
            assert indexer.db.add_documents.call_args_list[i] == call(batch)

        # Verify that sleep was called between batches.
        if len(expected_batches) > 1:
            assert mock_sleep.call_count == len(expected_batches) - 1
            mock_sleep.assert_has_calls([call(3)] * (len(expected_batches) - 1))

        # Verify that _copy_table was called to backup the table.
        mock_copy_table.assert_called_once_with(TABLE_NAME, BACKUP_TABLE_NAME, only_warn_if_table_inexistent=True)

        # Verify that db.delete was called to clear the original table.
        indexer.db.delete.assert_called_once_with(filter={})


def test_index_db_delete_error_triggers_restore(indexer, mock_hana_db):
    """
    In case of an error during db.delete,
    we want to ensure that the original data is restored from the backup table.
    """
    # Given:
    # Patch the delete to raise an exception.
    indexer.db.delete.side_effect = Exception("DB error")

    # Patch the functions that are called by index but are out of context of this test.
    indexer._load_documents = Mock(return_value=SINGLE_BATCH_DOCS)
    indexer.create_chunks = Mock(return_value=SINGLE_BATCH_DOCS)
    indexer._copy_table = Mock()

    # Patch the functions that are called in the except block and are thus object of this test.
    indexer._drop_table = Mock()
    indexer._rename_table = Mock()

    # When:
    # Run index and check the error handling.
    with pytest.raises(Exception, match="DB error"):
        indexer.index()

    # Then:
    # Ensure that methods to restore backup in the except block were called.
    indexer._drop_table.assert_called_once_with(TABLE_NAME, only_warn_if_table_inexistent=True)
    indexer._rename_table.assert_called_once_with(BACKUP_TABLE_NAME, TABLE_NAME, only_warn_if_table_inexistent=True)


def test_index_index_chunks_in_batches_error_triggers_restore(indexer, mock_hana_db):
    """
    In case of an error during _index_chunks_in_batches,
    we want to ensure that the original data is restored from the backup table.
    """
    # Given:
    # Patch the _index_chunks_in_batches method to raise an exception.
    indexer._index_chunks_in_batches = Mock(side_effect=Exception("index error"))

    # Patch the functions that are called by index but are out of context of this test.
    indexer._load_documents = Mock(return_value=SINGLE_BATCH_DOCS)
    indexer.create_chunks = Mock(return_value=SINGLE_BATCH_DOCS)
    indexer._copy_table = Mock()

    # Patch the functions that are called in the except block and are thus object of this test.
    indexer._drop_table = Mock()
    indexer._rename_table = Mock()

    # When:
    # Run index and check the error handling.
    with pytest.raises(Exception, match="index error"):
        indexer.index()

    # Then:
    # Ensure that methods to restore backup in the except block were called.
    indexer._drop_table.assert_called_once_with(TABLE_NAME, only_warn_if_table_inexistent=True)
    indexer._rename_table.assert_called_once_with(BACKUP_TABLE_NAME, TABLE_NAME, only_warn_if_table_inexistent=True)
