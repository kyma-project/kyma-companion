"""Unit tests for indexing.metadata.build_chunk_metadata."""

import pytest
from indexing.metadata import build_chunk_metadata

pytestmark = pytest.mark.unit

_SHA = "a" * 40
_DOCS_PATH = "/app/docs"


def _make_manifest(module: str, repo_url: str, commit: str = _SHA) -> dict:
    return {
        module: {
            "repo_url": repo_url,
            "commit": commit,
            "fetched_at": "2026-01-01T00:00:00+00:00",
        }
    }


class TestBuildChunkMetadataSiteRepo:
    """Repos published on kyma-project.io as external-content.

    deploy.yml copies <repo>/docs/user/ → external-content/<repo>/docs/
    so the URL strips docs/user/ and adds docs/ back.
    """

    def test_url_uses_kyma_site_external_content_path(self):
        manifest = _make_manifest("istio", "https://github.com/kyma-project/istio")
        source_path = f"{_DOCS_PATH}/istio/docs/user/01-overview.md"
        meta = build_chunk_metadata(source_path, _DOCS_PATH, manifest)

        assert meta["module"] == "istio"
        assert meta["path"] == "docs/user/01-overview.md"
        assert meta["repo"] == "https://github.com/kyma-project/istio"
        assert meta["commit"] == _SHA
        # docs/user/ is stripped; docs/ is added back (deploy.yml mapping)
        assert meta["url"] == "https://kyma-project.io/external-content/istio/docs/01-overview"
        assert meta["title"] is None
        assert meta["doc_type"] is None

    def test_url_strips_md_extension(self):
        manifest = _make_manifest("serverless", "https://github.com/kyma-project/serverless")
        source_path = f"{_DOCS_PATH}/serverless/docs/user/README.md"
        meta = build_chunk_metadata(source_path, _DOCS_PATH, manifest)

        assert meta["url"] == "https://kyma-project.io/external-content/serverless/docs/README"

    def test_url_strips_docs_prefix_only(self):
        """Files at docs/ root (no user/ sub-dir) still get the docs/ mapping."""
        manifest = _make_manifest("busola", "https://github.com/kyma-project/busola")
        # busola indexes docs/user/* but some repos only have docs/
        source_path = f"{_DOCS_PATH}/busola/docs/intro.md"
        meta = build_chunk_metadata(source_path, _DOCS_PATH, manifest)

        assert meta["url"] == "https://kyma-project.io/external-content/busola/docs/intro"

    def test_url_path_not_under_docs(self):
        """Files not under docs/ at all fall back gracefully -- file name only."""
        manifest = _make_manifest("busola", "https://github.com/kyma-project/busola")
        source_path = f"{_DOCS_PATH}/busola/README.md"
        meta = build_chunk_metadata(source_path, _DOCS_PATH, manifest)

        # No docs/ prefix found -- file name used directly
        assert meta["url"] == "https://kyma-project.io/external-content/busola/docs/README"


class TestBuildChunkMetadataKymaMonoRepo:
    """The 'kyma' mono-repo: served at the site root, strips the leading docs/ segment."""

    def test_url_strips_docs_prefix(self):
        manifest = _make_manifest("kyma", "https://github.com/kyma-project/kyma")
        source_path = f"{_DOCS_PATH}/kyma/docs/01-overview/README.md"
        meta = build_chunk_metadata(source_path, _DOCS_PATH, manifest)

        assert meta["module"] == "kyma"
        assert meta["url"] == "https://kyma-project.io/01-overview/README"

    def test_url_no_docs_prefix_falls_back(self):
        """Files not under docs/ are served at the site root without stripping."""
        manifest = _make_manifest("kyma", "https://github.com/kyma-project/kyma")
        source_path = f"{_DOCS_PATH}/kyma/README.md"
        meta = build_chunk_metadata(source_path, _DOCS_PATH, manifest)

        assert meta["url"] == "https://kyma-project.io/README"


class TestBuildChunkMetadataGitHubFallback:
    """Repos not in the site list fall back to a GitHub blob URL."""

    def test_url_is_github_blob(self):
        manifest = _make_manifest("warden", "https://github.com/kyma-project/warden")
        source_path = f"{_DOCS_PATH}/warden/docs/user/guide.md"
        meta = build_chunk_metadata(source_path, _DOCS_PATH, manifest)

        assert meta["url"] == f"https://github.com/kyma-project/warden/blob/{_SHA}/docs/user/guide.md"
        assert meta["commit"] == _SHA
        assert meta["repo"] == "https://github.com/kyma-project/warden"

    def test_url_is_none_when_no_repo_url(self):
        manifest = {"unknown-repo": {"repo_url": "", "commit": _SHA, "fetched_at": ""}}
        source_path = f"{_DOCS_PATH}/unknown-repo/doc.md"
        meta = build_chunk_metadata(source_path, _DOCS_PATH, manifest)

        assert meta["url"] is None


class TestBuildChunkMetadataMissingManifest:
    """When manifest is None (old fetch output), graceful fallback to local path."""

    def test_falls_back_to_local_path(self):
        source_path = f"{_DOCS_PATH}/istio/docs/user/01-overview.md"
        meta = build_chunk_metadata(source_path, _DOCS_PATH, None)

        assert meta["module"] == "istio"
        assert meta["path"] == "docs/user/01-overview.md"
        assert meta["repo"] is None
        assert meta["commit"] is None
        assert meta["url"] == source_path
        assert meta["title"] is None
        assert meta["doc_type"] is None

    def test_module_missing_from_manifest_falls_back(self):
        """Module not in manifest warns and falls back, even if manifest itself exists."""
        manifest = _make_manifest("other-module", "https://github.com/kyma-project/other")
        source_path = f"{_DOCS_PATH}/istio/docs/user/guide.md"
        meta = build_chunk_metadata(source_path, _DOCS_PATH, manifest)

        assert meta["repo"] is None
        assert meta["commit"] is None
        assert meta["url"] == source_path
