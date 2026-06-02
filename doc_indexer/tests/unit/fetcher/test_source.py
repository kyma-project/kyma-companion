import os

import pytest
from fetcher.source import DocumentsSource, get_documents_sources
from pydantic import ValidationError

pytestmark = pytest.mark.unit

VALID_SOURCE_DEFAULTS = {
    "source_type": "Github",
    "url": "https://github.com/kyma-project/kyma",
}


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


@pytest.mark.parametrize("name", ["kyma-docs", "my_source", "source123", "a"])
def test_documents_source_valid_names(name):
    source = DocumentsSource(name=name, **VALID_SOURCE_DEFAULTS)
    assert source.name == name


@pytest.mark.parametrize(
    "name",
    [
        "../evil",
        "../../etc/passwd",
        "foo/bar",
        "foo\\bar",
        ".",
        "",
        "   ",
    ],
)
def test_documents_source_invalid_names(name):
    with pytest.raises(ValidationError):
        DocumentsSource(name=name, **VALID_SOURCE_DEFAULTS)
