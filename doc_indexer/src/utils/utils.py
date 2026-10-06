import os
import re
import shutil
import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from http.client import HTTPMessage
from typing import IO
from urllib.parse import urlparse

from decouple import config

from utils.logging import get_logger

logger = get_logger(__name__)

# Only GitHub is supported as a document source (see fetcher.source.SourceType).
# codeload serves a gzipped tarball of any ref over anonymous HTTPS.
_CODELOAD_HOST = "codeload.github.com"
_ALLOWED_REPO_HOSTS = {"github.com", "www.github.com"}
_MIN_URL_PATH_PARTS = 2

# GitHub Enterprise host for SAP-internal repos (e.g. kyma/docusaurus-docs).
# Private repos require a token; the host is allow-listed via config so the
# default (empty) keeps the fetcher public-only for the kyma_docs pipeline.
# Read lazily (not at import) because settings.load_env_from_json populates the
# environment from config.json only after this module is first imported.


def _enterprise_host() -> str:
    """Configured GitHub Enterprise host, lower-cased; empty if unset."""
    return str(config("GITHUB_ENTERPRISE_HOST", default="")).strip().lower()


def _github_token() -> str:
    """Configured GitHub token for enterprise auth; empty if unset."""
    return str(config("GITHUB_TOKEN", default="")).strip()


# codeload tarballs are produced by `git archive`, which writes a pax global header
# with `comment=<full commit sha>`. The top-level directory is named "<repo>-<ref>"
# (e.g. "istio-HEAD", "istio-main"), so it only contains the sha when a sha was requested.
_COMMIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
# GitHub/GHE REST API tarballs name the top-level dir "<owner>-<repo>-<short_sha>"
# using an abbreviated (commonly 7-char) commit sha, so the directory-name
# fallback must accept abbreviated hashes, not just the full 40-char form.
_DIR_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")


class _StripAuthOnCrossHostRedirect(urllib.request.HTTPRedirectHandler):
    """Redirect handler that drops the Authorization header on a host change.

    urllib copies request headers (including a bearer token) onto the redirected
    request. GHE/GitHub tarball endpoints redirect to a signed download URL that
    does not need the token, so stripping it on a cross-host redirect prevents
    leaking the enterprise token to a different (e.g. storage/CDN) host while
    keeping it for same-host redirects that may still require it.
    """

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        """Build the redirected request, stripping auth when the host differs."""
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req is not None:
            orig_host = urlparse(req.full_url).netloc.lower()
            new_host = urlparse(newurl).netloc.lower()
            if orig_host != new_host:
                new_req.headers.pop("Authorization", None)
                new_req.headers.pop("authorization", None)
        return new_req


# Install a process-wide opener so urllib.request.urlopen strips the enterprise
# token on cross-host redirects (see _StripAuthOnCrossHostRedirect).
urllib.request.install_opener(urllib.request.build_opener(_StripAuthOnCrossHostRedirect))


@dataclass
class DownloadResult:
    """Result of a repository download, bundling the local path and the resolved commit sha."""

    path: str
    commit: str


def _parse_github_repo(repo_url: str) -> tuple[str, str, str]:
    """Extract (host, owner, repo) from a GitHub URL, rejecting anything else.

    Accepts public ``github.com`` and, when configured, the SAP GitHub
    Enterprise host in ``GITHUB_ENTERPRISE_HOST``.
    """
    parsed = urlparse(repo_url)
    host = parsed.netloc.lower()
    allowed = set(_ALLOWED_REPO_HOSTS)
    enterprise_host = _enterprise_host()
    if enterprise_host:
        allowed.add(enterprise_host)
    if parsed.scheme != "https" or host not in allowed:
        raise ValueError(f"unsupported repository URL (allowed hosts: {sorted(allowed)}): {repo_url}")
    parts = parsed.path.removesuffix(".git").strip("/").split("/")
    if len(parts) != _MIN_URL_PATH_PARTS or not all(parts) or any(p == ".." for p in parts):
        raise ValueError(f"cannot parse owner/repo from URL: {repo_url}")
    return host, parts[0], parts[1]


def _archive_url(host: str, owner: str, repo: str, ref: str) -> str:
    """Return the tarball URL for a ref.

    Public github.com is served by codeload; GitHub Enterprise Server exposes
    the archive through its REST API tarball endpoint, which honours the
    Authorization header for private repos.
    """
    if host in _ALLOWED_REPO_HOSTS:
        return f"https://{_CODELOAD_HOST}/{owner}/{repo}/tar.gz/{ref}"
    # GitHub Enterprise Server API v3 tarball endpoint.
    return f"https://{host}/api/v3/repos/{owner}/{repo}/tarball/{ref}"


def _request_headers(host: str) -> dict[str, str]:
    """Build request headers, adding bearer auth for the enterprise host."""
    headers = {"User-Agent": "kyma-companion-doc-indexer"}
    token = _github_token()
    enterprise_host = _enterprise_host()
    if token and enterprise_host and host == enterprise_host:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def download_repo(repo_url: str, dest_dir: str, ref: str = "HEAD") -> DownloadResult:
    """Download a GitHub repository tarball and extract it, returning path and commit sha.

    Replaces `git clone`: fetches the codeload tarball for the given ref over
    anonymous HTTPS and extracts it so that repository files sit directly under
    the returned path (the tarball's top-level `<repo>-<ref>/` wrapper is
    stripped), matching the layout the Scroller expects.

    The commit sha is read from the tarball's pax global header (`comment`),
    which `git archive` sets to the resolved commit. When absent (e.g. GHE API
    tarballs), it falls back to the trailing (possibly abbreviated) sha in the
    top-level directory name. Raises RuntimeError if neither yields a hex sha.
    """
    host, owner, repo = _parse_github_repo(repo_url)
    repo_path = os.path.join(dest_dir, repo)
    os.makedirs(dest_dir, exist_ok=True)
    if os.path.exists(repo_path):
        # Let rmtree raise on failure: a leftover repo_path would make the
        # shutil.move below nest the extract inside it (<dest>/<repo>/<repo>-<sha>),
        # silently breaking the layout the Scroller expects.
        shutil.rmtree(repo_path)

    tar_url = _archive_url(host, owner, repo, ref)
    logger.info("Downloading repository", extra={"url": tar_url, "dest": repo_path})

    with tempfile.TemporaryDirectory(dir=dest_dir) as staging:
        tar_path = os.path.join(staging, "repo.tar.gz")
        req = urllib.request.Request(tar_url, headers=_request_headers(host))
        try:
            with urllib.request.urlopen(req, timeout=120) as resp, open(tar_path, "wb") as fh:  # noqa: S310
                shutil.copyfileobj(resp, fh)
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"failed to download {tar_url}: HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"failed to download {tar_url}: {exc.reason}") from exc

        with tarfile.open(tar_path, "r:gz") as tf:
            commit = tf.pax_headers.get("comment", "")
            tf.extractall(staging, filter="data")  # filter="data" blocks path traversal (py3.12+)

        # The archive extracts to a single top-level dir named "<repo>-<ref>"
        # (public codeload) or "<owner>-<repo>-<sha>" (GHE API tarball).
        extracted = [e for e in os.listdir(staging) if os.path.isdir(os.path.join(staging, e))]
        if len(extracted) != 1:
            raise RuntimeError(f"unexpected tarball layout for {tar_url}: {extracted}")

        # Prefer the pax global header sha (set by `git archive`). GHE API
        # tarballs may omit it, so fall back to the trailing sha in the
        # top-level directory name before failing.
        if not _COMMIT_SHA_RE.match(commit):
            trailing = extracted[0].rsplit("-", 1)[-1]
            if _DIR_SHA_RE.match(trailing):
                commit = trailing
            else:
                raise RuntimeError(
                    f"cannot read commit sha for {tar_url}: pax comment={commit!r}, "
                    f"dir={extracted[0]!r} (expected 7-40 hex chars)"
                )

        shutil.move(os.path.join(staging, extracted[0]), repo_path)

    logger.info("Repository downloaded successfully", extra={"url": tar_url, "dest": repo_path, "commit": commit})
    return DownloadResult(path=repo_path, commit=commit)


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
