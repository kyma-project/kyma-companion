import os

import pytest
from fetcher.source import get_documents_sources

pytestmark = pytest.mark.unit


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


def test_documents_source_audience_doc_type_defaults():
    """Sources default to public audience and no doc_type for the kyma_docs pipeline."""
    from fetcher.source import DocumentsSource, SourceType

    source = DocumentsSource(
        name="istio", source_type=SourceType.GITHUB, url="https://github.com/kyma-project/istio.git"
    )

    assert source.audience == ["public"]
    assert source.doc_type is None


def test_documents_source_audience_doc_type_override():
    """Internal/ops sources can set audience and doc_type."""
    from fetcher.source import DocumentsSource, SourceType

    source = DocumentsSource(
        name="sre-runbooks",
        source_type=SourceType.GITHUB,
        url="https://github.tools.sap/kyma/docusaurus-docs.git",
        audience=["internal"],
        doc_type="runbook",
    )

    assert source.audience == ["internal"]
    assert source.doc_type == "runbook"


def test_get_ops_documents_sources(root_tests_path):
    """The ops_docs sources file parses and carries internal audience."""
    ops_path = os.path.join(root_tests_path, "..", "ops_docs_sources.json")
    result = get_documents_sources(ops_path)

    expected_source_count = 5
    assert len(result) == expected_source_count
    names = {s.name for s in result}
    assert names == {
        "sre-runbooks",
        "on-call-guides",
        "gardener",
        "orchestration-operator",
        "kubeconfig-service",
    }
    for source in result:
        assert source.audience == ["internal"]
