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
    ],
)
def test_parse_github_repo_rejected(given_url):
    with pytest.raises(ValueError):
        _parse_github_repo(given_url)


def _make_repo_tarball(top_dir: str, files: dict[str, str]) -> bytes:
    """Build an in-memory .tar.gz that extracts to a single top-level dir, like codeload."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
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
    # Given: a codeload-style tarball whose top dir is "<repo>-<sha>"
    repo_url = "https://github.com/kyma-project/eventing-manager.git"
    tar_bytes = _make_repo_tarball(
        "eventing-manager-abc123",
        {"README.md": "# hello", "docs/user/guide.md": "guide"},
    )
    dest = str(tmp_path)

    # When
    with patch("utils.utils.urllib.request.urlopen", return_value=_FakeResponse(tar_bytes)):
        repo_path = download_repo(repo_url, dest)

    # Then: files live directly under <dest>/<repo>, wrapper dir stripped
    assert repo_path == os.path.join(dest, "eventing-manager")
    assert os.path.isfile(os.path.join(repo_path, "README.md"))
    assert os.path.isfile(os.path.join(repo_path, "docs", "user", "guide.md"))
    # staging temp dir is cleaned up
    assert set(os.listdir(dest)) == {"eventing-manager"}


def test_download_repo_replaces_existing_dir(tmp_path):
    repo_url = "https://github.com/kyma-project/eventing-manager.git"
    dest = str(tmp_path)
    stale = os.path.join(dest, "eventing-manager")
    os.makedirs(stale)
    with open(os.path.join(stale, "old.md"), "w") as fh:
        fh.write("stale")

    tar_bytes = _make_repo_tarball("eventing-manager-def456", {"new.md": "fresh"})

    with patch("utils.utils.urllib.request.urlopen", return_value=_FakeResponse(tar_bytes)):
        repo_path = download_repo(repo_url, dest)

    assert os.path.isfile(os.path.join(repo_path, "new.md"))
    assert not os.path.exists(os.path.join(repo_path, "old.md"))
