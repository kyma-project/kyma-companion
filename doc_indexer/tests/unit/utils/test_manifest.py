import json
from pathlib import Path

import pytest
from utils.manifest import has_manifest, load_manifest_documents

pytestmark = pytest.mark.unit


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def artifact_dir(tmp_path):
    """A tiny synthetic pinakes artifact: two sources, one residue file, one excluded page.

    Layout (SPEC 2.3):
        manifest.json
        istio/meta.json, docs/user/README.md, docs/user/second.md
        api-gateway/meta.json, docs/user/overview.md
        _residue/istio/docs/user/leftover.md   (not in the manifest -- must never be read)
        decisions.jsonl                         (excludes istio::docs/user/second.md)
    """
    root = tmp_path / "artifact"

    manifest = {
        "version": 1,
        "generated_at": "2026-09-16T00:00:00Z",
        "sources": {
            "istio": {
                "commit": "abc123",
                "pages": {
                    "docs/user/README.md": {
                        "title": "Istio Module",
                        "doc_type": "concept",
                        "section": "",
                        "sha256": "sha-readme",
                        "selected_by": "resolver",
                    },
                    "docs/user/second.md": {
                        "title": "Second Page",
                        "doc_type": "howto",
                        "section": "Guides",
                        "sha256": "sha-second",
                        "selected_by": "resolver",
                    },
                },
            },
            "api-gateway": {
                "commit": "def456",
                "pages": {
                    "docs/user/overview.md": {
                        "title": "API Gateway Overview",
                        "doc_type": "concept",
                        "section": "",
                        "sha256": "sha-overview",
                        "selected_by": "resolver",
                    }
                },
            },
        },
    }
    _write(root / "manifest.json", json.dumps(manifest))

    _write(
        root / "istio" / "meta.json",
        json.dumps(
            {
                "repo": "kyma-project/istio",
                "module": "istio",
                "base_url": "https://github.com/kyma-project/istio/blob/abc123",
                "commit": "abc123",
            }
        ),
    )
    _write(root / "istio" / "docs" / "user" / "README.md", "# Istio Module\nOverview content.")
    _write(root / "istio" / "docs" / "user" / "second.md", "# Second Page\nGuide content.")

    _write(
        root / "api-gateway" / "meta.json",
        json.dumps(
            {
                "repo": "kyma-project/api-gateway",
                "module": "api-gateway",
                "base_url": "https://github.com/kyma-project/api-gateway/blob/def456",
                "commit": "def456",
            }
        ),
    )
    _write(root / "api-gateway" / "docs" / "user" / "overview.md", "# API Gateway Overview\nOverview content.")

    # Residue: left out by the resolver, never listed in the manifest -- must not be read.
    _write(root / "_residue" / "istio" / "docs" / "user" / "leftover.md", "# Leftover\nShould never be indexed.")

    # Exclude istio::docs/user/second.md via a still-valid decision (sha256 matches the manifest).
    decision = {
        "id": "istio::docs/user/second.md",
        "sha256": "sha-second",
        "decision": "exclude",
        "reason": "duplicate of another page",
        "by": "test",
        "at": "2026-09-16T00:00:00Z",
    }
    _write(root / "decisions.jsonl", json.dumps(decision) + "\n")

    return root


def test_has_manifest_true_for_artifact_dir(artifact_dir):
    assert has_manifest(str(artifact_dir)) is True


def test_has_manifest_false_without_manifest_json(tmp_path):
    assert has_manifest(str(tmp_path)) is False


def test_has_manifest_false_for_empty_path():
    assert has_manifest("") is False


def test_load_manifest_documents_only_reads_manifest_pages(artifact_dir):
    """Residue and excluded pages are skipped; only the two remaining manifest pages load."""
    docs = load_manifest_documents(str(artifact_dir))

    page_ids = {doc.metadata["page_id"] for doc in docs}
    assert page_ids == {"istio::docs/user/README.md", "api-gateway::docs/user/overview.md"}

    contents = {doc.metadata["page_id"]: doc.page_content for doc in docs}
    assert "Overview content." in contents["istio::docs/user/README.md"]
    assert all("Leftover" not in doc.page_content for doc in docs)
    assert all("Guide content." not in doc.page_content for doc in docs)


def test_load_manifest_documents_metadata(artifact_dir):
    docs = load_manifest_documents(str(artifact_dir))
    by_id = {doc.metadata["page_id"]: doc for doc in docs}

    istio_doc = by_id["istio::docs/user/README.md"]
    assert istio_doc.metadata["module"] == "istio"
    assert istio_doc.metadata["repo"] == "kyma-project/istio"
    assert istio_doc.metadata["commit"] == "abc123"
    assert istio_doc.metadata["url"] == "https://github.com/kyma-project/istio/blob/abc123/docs/user/README.md"
    assert istio_doc.metadata["title"] == "Istio Module"
    assert istio_doc.metadata["doc_type"] == "concept"
    assert istio_doc.metadata["section"] == ""
    assert istio_doc.metadata["path"] == "docs/user/README.md"
    assert istio_doc.metadata["sha256"] == "sha-readme"

    gateway_doc = by_id["api-gateway::docs/user/overview.md"]
    assert gateway_doc.metadata["module"] == "api-gateway"
    assert gateway_doc.metadata["doc_type"] == "concept"


def test_load_manifest_documents_stale_decision_keeps_page(artifact_dir):
    """A decision whose sha256 no longer matches the manifest page is stale and ignored."""
    decisions_path = artifact_dir / "decisions.jsonl"
    stale = {
        "id": "istio::docs/user/second.md",
        "sha256": "sha-second-OLD",  # no longer matches the manifest's "sha-second"
        "decision": "exclude",
        "reason": "stale",
        "by": "test",
        "at": "2026-09-16T00:00:00Z",
    }
    decisions_path.write_text(json.dumps(stale) + "\n", encoding="utf-8")

    docs = load_manifest_documents(str(artifact_dir))
    page_ids = {doc.metadata["page_id"] for doc in docs}
    assert "istio::docs/user/second.md" in page_ids


def test_load_manifest_documents_skips_source_without_meta_json(artifact_dir):
    (artifact_dir / "api-gateway" / "meta.json").unlink()

    docs = load_manifest_documents(str(artifact_dir))
    page_ids = {doc.metadata["page_id"] for doc in docs}
    assert page_ids == {"istio::docs/user/README.md"}
