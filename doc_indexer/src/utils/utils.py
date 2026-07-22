import os
import re
import shutil
import tarfile
import tempfile
import urllib.request
from urllib.parse import urlparse

from utils.logging import get_logger

logger = get_logger(__name__)

# Only GitHub is supported as a document source (see fetcher.source.SourceType).
# codeload serves a gzipped tarball of any ref over anonymous HTTPS.
_CODELOAD_HOST = "codeload.github.com"
_ALLOWED_REPO_HOSTS = {"github.com", "www.github.com"}
_MIN_URL_PATH_PARTS = 2


def _parse_github_repo(repo_url: str) -> tuple[str, str]:
    """Extract (owner, repo) from a GitHub URL, rejecting anything else."""
    parsed = urlparse(repo_url)
    if parsed.scheme != "https" or parsed.netloc.lower() not in _ALLOWED_REPO_HOSTS:
        raise ValueError(f"unsupported repository URL (only github.com is allowed): {repo_url}")
    parts = parsed.path.removesuffix(".git").strip("/").split("/")
    if len(parts) < _MIN_URL_PATH_PARTS or not all(parts[:_MIN_URL_PATH_PARTS]):
        raise ValueError(f"cannot parse owner/repo from URL: {repo_url}")
    return parts[0], parts[1]


def download_repo(repo_url: str, dest_dir: str, ref: str = "HEAD") -> str:
    """Download a GitHub repository tarball and extract it, returning the path.

    Replaces `git clone`: fetches the codeload tarball for the given ref over
    anonymous HTTPS and extracts it so that repository files sit directly under
    the returned path (the tarball's top-level `<repo>-<ref>/` wrapper is
    stripped), matching the layout the Scroller expects.
    """
    owner, repo = _parse_github_repo(repo_url)
    repo_path = os.path.join(dest_dir, repo)
    if os.path.exists(repo_path):
        # Let rmtree raise on failure: a leftover repo_path would make the
        # shutil.move below nest the extract inside it (<dest>/<repo>/<repo>-<sha>),
        # silently breaking the layout the Scroller expects.
        shutil.rmtree(repo_path)

    tar_url = f"https://{_CODELOAD_HOST}/{owner}/{repo}/tar.gz/{ref}"
    logger.info("Downloading repository", extra={"url": tar_url, "dest": repo_path})

    with tempfile.TemporaryDirectory(dir=dest_dir) as staging:
        tar_path = os.path.join(staging, "repo.tar.gz")
        req = urllib.request.Request(tar_url, headers={"User-Agent": "kyma-companion-doc-indexer"})
        with urllib.request.urlopen(req, timeout=120) as resp, open(tar_path, "wb") as fh:  # noqa: S310
            shutil.copyfileobj(resp, fh)

        with tarfile.open(tar_path, "r:gz") as tf:
            tf.extractall(staging, filter="data")  # filter="data" blocks path traversal (py3.12+)

        # The archive extracts to a single top-level dir named "<repo>-<ref-or-sha>".
        entries = [e for e in os.listdir(staging) if e != "repo.tar.gz"]
        extracted = [e for e in entries if os.path.isdir(os.path.join(staging, e))]
        if len(extracted) != 1:
            raise RuntimeError(f"unexpected tarball layout for {tar_url}: {extracted}")
        shutil.move(os.path.join(staging, extracted[0]), repo_path)

    logger.info("Repository downloaded successfully", extra={"url": tar_url, "dest": repo_path})
    return repo_path


def sanitize_table_name(name: str) -> str:
    """Replace characters illegal in HANA table names with underscores.

    HANA table names may only contain letters, digits, and underscores.
    Any other character (dots, hyphens, slashes, etc.) is replaced with '_'.
    Leading digits are prefixed with '_' to avoid invalid identifiers.

    Example: 'release-0.5.2_e2e' -> 'release_0_5_2_e2e'
    """
    sanitized = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if sanitized and sanitized[0].isdigit():
        sanitized = f"_{sanitized}"
    return sanitized
