"""Helpers for building per-chunk metadata from a fetch manifest."""

import os

from utils.logging import get_logger

logger = get_logger(__name__)

# Repos whose docs are published on kyma-project.io as external-content.
# Source of truth: kyma-project/kyma/.github/workflows/deploy.yml
_KYMA_SITE_REPOS = frozenset(
    [
        "btp-manager",
        "istio",
        "serverless",
        "telemetry-manager",
        "eventing-manager",
        "api-gateway",
        "nats-manager",
        "application-connector-manager",
        "keda-manager",
        "cloud-manager",
        "docker-registry",
        "busola",
        "cli",
        "registry-proxy",
        "community-modules",
        "registry-cache",
    ]
)

# The special "kyma" mono-repo whose docs are served at the root of kyma-project.io.
_KYMA_MONO_REPO = "kyma"


def build_chunk_metadata(
    source_path: str,
    docs_path: str,
    manifest: dict[str, dict[str, str | None]] | None,
) -> dict[str, str | None]:
    """Build metadata for a single chunk based on its source path and the fetch manifest.

    Args:
        source_path: Absolute (or docs_path-relative) path to the source markdown file.
        docs_path: Root directory that was passed to the indexer (all modules live
            directly beneath it).
        manifest: Contents of ``manifest.json`` as written by
            :meth:`~fetcher.fetcher.DocumentsFetcher.run`, keyed by module name.
            May be ``None`` when indexing output produced by an old fetcher that
            did not write a manifest; in that case ``repo`` / ``commit`` are set
            to ``None`` and ``url`` falls back to the local path.

    Returns:
        A dict with keys ``module``, ``path``, ``repo``, ``commit``, ``url``,
        ``title`` (always ``None`` here -- the caller fills it in), and
        ``doc_type`` (always ``None`` for now).
    """
    # Derive the relative path from docs_path.
    rel = os.path.relpath(source_path, docs_path)
    parts = rel.split(os.sep, 1)
    module = parts[0]
    doc_rel_path = parts[1] if len(parts) > 1 else ""

    # Normalise to forward slashes for URLs / storage.
    doc_rel_path = doc_rel_path.replace(os.sep, "/")

    if manifest is None or module not in manifest:
        if manifest is not None:
            logger.warning(
                "Module not found in manifest -- falling back to local path",
                extra={"module_name": module, "source": source_path},
            )
        else:
            logger.warning(
                "No manifest available -- falling back to local path",
                extra={"source": source_path},
            )
        return {
            "module": module,
            "path": doc_rel_path,
            "repo": None,
            "commit": None,
            "url": source_path,
            "title": None,
            "doc_type": None,
        }

    entry = manifest[module]
    repo_url = entry.get("repo_url") or ""
    commit = entry.get("commit")

    url = _build_url(module, doc_rel_path, repo_url, commit)

    return {
        "module": module,
        "path": doc_rel_path,
        "repo": repo_url or None,
        "commit": commit,
        "url": url,
        "title": None,
        "doc_type": None,
    }


def _build_url(module: str, doc_rel_path: str, repo_url: str, commit: str | None) -> str | None:
    """Construct the canonical public URL for a document.

    Three cases:

    - kyma-project.io external-content repos: the deploy workflow copies
      ``<repo>/docs/user/`` → ``external-content/<repo>/docs/``, so the
      ``docs/user/`` prefix from the repo path is replaced with ``docs/``.
      URL: ``https://kyma-project.io/external-content/<repo>/docs/<filename>``
    - The ``kyma`` mono-repo: ``https://kyma-project.io/<path under docs/ without .md>``
    - Everything else: ``<repo_url>/blob/<commit>/<path>`` (GitHub blob URL,
      extension preserved so the link is a valid GitHub file reference).
    """
    # Strip trailing .md for web page URLs (site repos and mono-repo).
    path_no_ext = doc_rel_path.removesuffix(".md")

    if module in _KYMA_SITE_REPOS:
        # deploy.yml: docs/user/<file> → external-content/<repo>/docs/<file>
        docs_user_prefix = "docs/user/"
        docs_prefix = "docs/"
        if path_no_ext.startswith(docs_user_prefix):
            site_file = path_no_ext[len(docs_user_prefix) :]
        elif path_no_ext.startswith(docs_prefix):
            site_file = path_no_ext[len(docs_prefix) :]
        else:
            site_file = path_no_ext
        return f"https://kyma-project.io/external-content/{module}/docs/{site_file}"

    if module == _KYMA_MONO_REPO:
        # The kyma mono-repo docs sit under docs/ in the repo; the site serves them
        # without the leading "docs/" segment.
        docs_prefix = "docs/"
        site_path = path_no_ext[len(docs_prefix) :] if path_no_ext.startswith(docs_prefix) else path_no_ext
        return f"https://kyma-project.io/{site_path}"

    # Fallback: GitHub blob URL (preserves extension -- it's a file reference, not a web page).
    if not repo_url or not commit:
        return None
    return f"{repo_url}/blob/{commit}/{doc_rel_path}"
