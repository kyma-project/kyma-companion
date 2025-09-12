from pathlib import Path
from unittest.mock import patch

import pytest
from langchain.schema import Document
from utils.documents import load_documents


@pytest.fixture
def sample_docs_dir(tmp_path):
    # Create a temporary directory with some test files
    docs_dir = tmp_path / "test_docs"
    docs_dir.mkdir()
    return str(docs_dir)


@pytest.fixture
def create_test_file(sample_docs_dir):
    def _create_file(filename: str, content: str):
        file_path = Path(sample_docs_dir) / filename
        # Create parent directories if they don't exist
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

    return _create_file


@pytest.mark.parametrize(
    "name, test_case",
    [
        # Success cases
        (
            "single file",
            {
                "files": [("test1.md", "Test content 1")],
                "expected_count": 1,
                "expected_content": ["Test content 1"],
            },
        ),
        (
            "multiple files",
            {
                "files": [
                    ("test2.md", "Test content 2"),
                    ("test3.md", "Test content 3"),
                ],
                "expected_count": 2,
                "expected_content": [
                    "Test content 2",
                    "Test content 3",
                ],
            },
        ),
        (
            "empty directory",
            {
                "files": [],
                "expected_count": 0,
                "expected_content": None,
            },
        ),
        (
            "nested folders",
            {
                "files": [
                    ("folder1/test1.md", "Content in folder1"),
                    ("folder1/folder2/test2.md", "Content in folder2"),
                    ("folder1/folder2/folder3/test3.md", "Content in folder3"),
                ],
                "expected_count": 3,
                "expected_content": [
                    "Content in folder1",
                    "Content in folder2",
                    "Content in folder3",
                ],
            },
        ),
        (
            "mixed files and folders",
            {
                "files": [
                    ("root.md", "Root content"),
                    ("folder1/nested.md", "Nested content"),
                    ("folder2/deep/file.md", "Deep content"),
                ],
                "expected_count": 3,
                "expected_content": ["Root content", "Nested content", "Deep content"],
            },
        ),
        (
            "empty folders",
            {
                "files": [
                    ("empty_folder/.gitkeep", ""),
                    ("folder1/test.md", "Some content"),
                    ("folder1/empty_subfolder/.gitkeep", ""),
                ],
                "expected_count": 1,  # .gitkeep files are typically ignored
                "expected_content": ["Some content"],
            },
        ),
        # Error cases
        (
            "nonexistent directory",
            {
                "path": "nonexistent_directory",
                "expected_error": FileNotFoundError,
            },
        ),
        (
            "empty path",
            {
                "path": "",
                "expected_error": ValueError,
            },
        ),
        (
            "permission error",
            {
                "mock_error": PermissionError("Access denied"),
                "expected_error": Exception,
            },
        ),
    ],
)
def test_load_documents(sample_docs_dir, create_test_file, name, test_case):
    # Handle mocked error cases
    if "mock_error" in test_case:
        with patch("utils.documents.DirectoryLoader") as mock_loader:
            mock_loader.return_value.load.side_effect = test_case["mock_error"]
            with pytest.raises(test_case["expected_error"]):
                load_documents("some_directory")
        return

    # Handle path error cases
    if "path" in test_case:
        with pytest.raises(test_case["expected_error"]):
            load_documents(test_case["path"])
        return

    # Handle success cases
    for filename, content in test_case["files"]:
        create_test_file(filename, content)

    docs = load_documents(sample_docs_dir)

    assert isinstance(docs, list)
    assert len(docs) == test_case["expected_count"]

    # Enhanced assertions for nested content
    if isinstance(test_case.get("expected_content"), list):
        # For test cases with multiple expected contents
        doc_contents = [doc.page_content for doc in docs]
        for expected in test_case["expected_content"]:
            assert expected in doc_contents
    elif test_case.get("expected_content"):
        # For backward compatibility with existing single-content test cases
        assert isinstance(docs[0], Document)
        assert test_case["expected_content"] in docs[0].page_content
