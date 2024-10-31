import os

import pytest
from fetcher.source import get_documents_sources


@pytest.fixture
def docs_sources_file_path(root_tests_path):
    """Return the path to the documents sources file."""
    return os.path.join(root_tests_path, "..", "docs_sources.json")


def test_get_documents_sources(docs_sources_file_path):
    """Test the get_documents_sources function."""
    # when
    result = get_documents_sources(docs_sources_file_path)

    # then
    # should be able to read the file.
    assert len(result) > 0
