from typing import Any
from unittest.mock import Mock, call, patch

import pytest
from indexing.indexer import MarkdownIndexer, create_chunks
from langchain_core.documents import Document

SINGLE_BATCH_DOCS = [Document(page_content="# My Header 1\nContent")]
MAIN_TABLE_NAME = "test_table"
TEMP_TABLE_NAME = "temp_table"
BACKUP_TABLE_NAME = "backup_table"
DROP_TABLE_CALL_COUNT = 2


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
        mock_instance.table_name = TEMP_TABLE_NAME
        yield mock


@pytest.fixture
def indexer(mock_embedding, mock_connection, mock_hana_db):
    return MarkdownIndexer(
        docs_path="",
        embedding=mock_embedding,
        connection=mock_connection,
        table_name=MAIN_TABLE_NAME,
        backup_table_name=BACKUP_TABLE_NAME,
        temp_table_name=TEMP_TABLE_NAME,
    )


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
            [
                Document(page_content=f"# Header {i}\nContent") for i in range(6)
            ],  # Assuming CHUNKS_BATCH_SIZE is 5
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
        patch(
            "indexing.indexer.create_chunks", return_value=expected_chunks
        ) as mock_create_chunks,
        patch("indexing.indexer.CHUNKS_BATCH_SIZE", 5),
        patch("time.sleep") as mock_sleep,
        patch.object(indexer, "_drop_table") as mock_drop_table,
        patch.object(indexer, "_rename_table") as mock_rename_table,
        patch.object(
            indexer, "_rename_table_with_backup"
        ) as mock_rename_table_with_backup,
    ):
        indexer.headers_to_split_on = headers_to_split_on
        indexer.index()

        # Verify create_chunks was called
        mock_create_chunks.assert_called_once_with(loaded_docs, headers_to_split_on)

        # Verify _drop_table was called twice: once for NEW_TABLE_NAME, once for ORIGINAL_TABLE_NAME
        assert mock_drop_table.call_count == DROP_TABLE_CALL_COUNT
        mock_drop_table.assert_any_call(TEMP_TABLE_NAME)
        mock_drop_table.assert_any_call(BACKUP_TABLE_NAME)

        # Verify _rename_table was called with NEW_TABLE_NAME and ORIGINAL_TABLE_NAME
        mock_rename_table.assert_called_once_with(MAIN_TABLE_NAME, BACKUP_TABLE_NAME)

        # Verify _rename_table_with_backup was called with ORIGINAL_TABLE_NAME and BACKUP_TABLE_NAME
        mock_rename_table_with_backup.assert_called_once_with(
            TEMP_TABLE_NAME, MAIN_TABLE_NAME, BACKUP_TABLE_NAME
        )

        # Calculate expected number of batches
        num_chunks = len(expected_chunks)
        batch_size = 5  # From the mocked CHUNKS_BATCH_SIZE
        expected_batches = [
            expected_chunks[i : i + batch_size]
            for i in range(0, num_chunks, batch_size)
        ]

        # Verify add_documents was called for each batch
        assert indexer.db.add_documents.call_count == len(expected_batches)
        for i, batch in enumerate(expected_batches):
            assert indexer.db.add_documents.call_args_list[i] == call(batch)

        # Verify sleep was called between batches
        if len(expected_batches) > 1:
            assert mock_sleep.call_count == len(expected_batches) - 1
            mock_sleep.assert_has_calls([call(3)] * (len(expected_batches) - 1))


def test_index_drop_table_error(indexer, mock_hana_db):
    loaded_docs = SINGLE_BATCH_DOCS
    expected_chunks = SINGLE_BATCH_DOCS

    with (
        patch.object(indexer, "_load_documents", return_value=loaded_docs),
        patch("indexing.indexer.create_chunks", return_value=expected_chunks),
        patch("indexing.indexer.CHUNKS_BATCH_SIZE", 5),
        patch("time.sleep"),
        patch.object(indexer, "_drop_table", side_effect=Exception("Drop table error")),
    ):
        with pytest.raises(Exception) as exc_info:
            indexer.index()
        assert "Drop table error" in str(exc_info.value)


def test_index_add_documents_error(indexer, mock_hana_db):
    loaded_docs = SINGLE_BATCH_DOCS
    expected_chunks = SINGLE_BATCH_DOCS
    indexer.db.add_documents.side_effect = Exception("Add documents error")

    with (
        patch.object(indexer, "_load_documents", return_value=loaded_docs),
        patch("indexing.indexer.create_chunks", return_value=expected_chunks),
        patch("indexing.indexer.CHUNKS_BATCH_SIZE", 5),
        patch("time.sleep"),
    ):
        with pytest.raises(Exception) as exc_info:
            indexer.index()
        assert exc_info.type is Exception
        assert str(exc_info.value) == "Add documents error"


def test_index_rename_table_error(indexer, mock_hana_db):
    loaded_docs = SINGLE_BATCH_DOCS
    expected_chunks = SINGLE_BATCH_DOCS

    with (
        patch.object(indexer, "_load_documents", return_value=loaded_docs),
        patch("indexing.indexer.create_chunks", return_value=expected_chunks),
        patch("indexing.indexer.CHUNKS_BATCH_SIZE", 5),
        patch("time.sleep"),
        patch.object(
            indexer, "_rename_table", side_effect=Exception("Rename table error")
        ),
    ):
        with pytest.raises(Exception) as exc_info:
            indexer.index()
        assert "Rename table error" in str(exc_info.value)


def test_index_rename_table_with_backup_error(indexer, mock_hana_db):
    loaded_docs = SINGLE_BATCH_DOCS
    expected_chunks = SINGLE_BATCH_DOCS

    # Patch _rename_table_with_backup to raise, and _rename_table to track calls
    with (
        patch.object(indexer, "_load_documents", return_value=loaded_docs),
        patch("indexing.indexer.create_chunks", return_value=expected_chunks),
        patch("indexing.indexer.CHUNKS_BATCH_SIZE", 5),
        patch("time.sleep"),
        patch.object(
            indexer,
            "_rename_table_with_backup",
            side_effect=Exception("Rename table with backup error"),
        ),
    ):
        with pytest.raises(Exception) as exc_info:
            indexer.index()
        assert "Rename table with backup error" in str(exc_info.value)
