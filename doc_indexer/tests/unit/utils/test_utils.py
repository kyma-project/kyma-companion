import io
import os
import tarfile
from unittest.mock import patch

import pytest

from utils.utils import _parse_github_repo, download_repo

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "given_url, expected",
    [
        ("https://github.com/kyma-project/eventing-manager.git", ("kyma-project", "eventing-manager")),
        ("https://github.com/kyma-project/eventing-manager", ("kyma-project", "eventing-manager")),
        ("https://github.com/SAP-docs/btp-cloud-platform.git", ("SAP-docs", "btp-cloud-platform")),
    ],
)
def test_parse_github_repo_valid(given_url, expected):
    assert _parse_github_repo(given_url) == expected


@pytest.mark.parametrize(
    "given_url",
    [
        "https://gitlab.com/kyma-project/eventing-manager.git",  # wrong host
        "git@github.com:kyma-project/eventing-manager.git",  # ssh scheme
        "https://github.com/only-owner",  # missing repo
        "ftp://github.com/a/b",  # bad scheme
        "https://github.com/owner/repo/tree/main",  # extra path segments
        "https://github.com/owner/../evil",  # path traversal attempt
        "https://github.com/../evil-repo",  # path traversal in owner position
    ],
)
def test_parse_github_repo_rejected(given_url):
    with pytest.raises(ValueError):
        _parse_github_repo(given_url)


_SHA = "a" * 40  # 40-char hex sha fixture


def _make_repo_tarball(top_dir: str, files: dict[str, str], commit: str | None = _SHA) -> bytes:
    """Build an in-memory .tar.gz like codeload: one top-level dir named "<repo>-<ref>" and,
    unless ``commit`` is None, a pax global header ``comment=<sha>`` as written by `git archive`.
    """
    buf = io.BytesIO()
    pax_headers = {"comment": commit} if commit is not None else {}
    with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.PAX_FORMAT, pax_headers=pax_headers) as tf:
        for rel_path, content in files.items():
            data = content.encode()
            info = tarfile.TarInfo(name=f"{top_dir}/{rel_path}")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class _FakeResponse(io.BytesIO):
    """Minimal context-manager wrapper mimicking urlopen's response object."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def test_download_repo_extracts_and_strips_wrapper(tmp_path):
    # Given: a codeload-style tarball whose top dir is "<repo>-<ref>" (default ref is HEAD)
    repo_url = "https://github.com/kyma-project/eventing-manager.git"
    tar_bytes = _make_repo_tarball(
        "eventing-manager-HEAD",
        {"README.md": "# hello", "docs/user/guide.md": "guide"},
    )
    dest = str(tmp_path)

    # When
    with patch("utils.utils.urllib.request.urlopen", return_value=_FakeResponse(tar_bytes)):
        result = download_repo(repo_url, dest)

    # Then: files live directly under <dest>/<repo>, wrapper dir stripped
    assert result.path == os.path.join(dest, "eventing-manager")
    assert result.commit == _SHA
    assert os.path.isfile(os.path.join(result.path, "README.md"))
    assert os.path.isfile(os.path.join(result.path, "docs", "user", "guide.md"))
    # staging temp dir is cleaned up
    assert set(os.listdir(dest)) == {"eventing-manager"}


def test_download_repo_replaces_existing_dir(tmp_path):
    repo_url = "https://github.com/kyma-project/eventing-manager.git"
    dest = str(tmp_path)
    stale = os.path.join(dest, "eventing-manager")
    os.makedirs(stale)
    with open(os.path.join(stale, "old.md"), "w") as fh:
        fh.write("stale")

    sha2 = "b" * 40
    tar_bytes = _make_repo_tarball("eventing-manager-HEAD", {"new.md": "fresh"}, commit=sha2)

    with patch("utils.utils.urllib.request.urlopen", return_value=_FakeResponse(tar_bytes)):
        result = download_repo(repo_url, dest)

    assert result.commit == sha2
    assert os.path.isfile(os.path.join(result.path, "new.md"))
    assert not os.path.exists(os.path.join(result.path, "old.md"))


def test_download_repo_creates_dest_dir(tmp_path):
    repo_url = "https://github.com/kyma-project/eventing-manager.git"
    dest = str(tmp_path / "nonexistent" / "nested")

    tar_bytes = _make_repo_tarball("eventing-manager-HEAD", {"README.md": "# hello"})

    with patch("utils.utils.urllib.request.urlopen", return_value=_FakeResponse(tar_bytes)):
        result = download_repo(repo_url, dest)

    assert os.path.isfile(os.path.join(result.path, "README.md"))
    assert result.commit == _SHA


def test_download_repo_works_for_named_ref_dir(tmp_path):
    """The top-level dir carries the ref name, not the sha; the sha comes from the pax header."""
    repo_url = "https://github.com/kyma-project/eventing-manager.git"
    tar_bytes = _make_repo_tarball("eventing-manager-main", {"README.md": "# hello"})

    with patch("utils.utils.urllib.request.urlopen", return_value=_FakeResponse(tar_bytes)):
        result = download_repo(repo_url, str(tmp_path), ref="main")

    assert result.commit == _SHA
    assert os.path.isfile(os.path.join(result.path, "README.md"))


def test_download_repo_raises_on_missing_commit_header(tmp_path):
    """download_repo raises RuntimeError when the tarball has no pax `comment` header."""
    repo_url = "https://github.com/kyma-project/eventing-manager.git"
    tar_bytes = _make_repo_tarball("eventing-manager-HEAD", {"README.md": "# hello"}, commit=None)

    with (
        patch("utils.utils.urllib.request.urlopen", return_value=_FakeResponse(tar_bytes)),
        pytest.raises(RuntimeError, match="cannot read commit sha"),
    ):
        download_repo(repo_url, str(tmp_path))


def test_download_repo_raises_on_malformed_commit_header(tmp_path):
    """download_repo raises RuntimeError when the pax `comment` header is not a 40-char hex sha."""
    repo_url = "https://github.com/kyma-project/eventing-manager.git"
    tar_bytes = _make_repo_tarball("eventing-manager-HEAD", {"README.md": "# hello"}, commit="not-a-sha")

    with (
        patch("utils.utils.urllib.request.urlopen", return_value=_FakeResponse(tar_bytes)),
        pytest.raises(RuntimeError, match="cannot read commit sha"),
    ):
        download_repo(repo_url, str(tmp_path))
