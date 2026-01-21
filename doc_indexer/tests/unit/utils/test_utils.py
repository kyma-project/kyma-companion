from unittest.mock import patch

import pytest

from utils.utils import clone_repo


@pytest.fixture()
def mock_subprocess_run():
    with patch("subprocess.run") as mock:
        yield mock


@pytest.fixture()
def mock_os_path_exists():
    with patch("os.path.exists") as mock:
        yield mock


@pytest.mark.parametrize(
    "given_repo_url, given_clone_dir, given_dir_exists, expected_repo_path",
    [
        # Test case when clone dir do not already exists.
        (
            "https://github.com/kyma-project/eventing-manager.git",
            "tmp/test_clone_repo",
            False,
            "tmp/test_clone_repo/eventing-manager",
        ),
        # Test case when clone dir already exists, should delete the existing dir before cloning.
        (
            "https://github.com/kyma-project/eventing-manager.git",
            "tmp/test_clone_repo",
            True,
            "tmp/test_clone_repo/eventing-manager",
        ),
    ],
)
def test_clone_repo(
    mock_subprocess_run,
    mock_os_path_exists,
    given_repo_url,
    given_clone_dir,
    given_dir_exists,
    expected_repo_path,
):
    # Given
    mock_os_path_exists.return_value = given_dir_exists

    # When
    repo_path = clone_repo(given_repo_url, given_clone_dir)

    # Then
    if given_dir_exists:
        mock_os_path_exists.assert_called_once_with(expected_repo_path)
    mock_subprocess_run.assert_called_once_with(["git", "clone", given_repo_url, expected_repo_path])
    assert repo_path == expected_repo_path
