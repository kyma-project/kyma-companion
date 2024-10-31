import os
import shutil
import subprocess


def clone_repo(repo_url: str, clone_dir: str) -> str:
    """Clones the git repository and returns the path."""
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    repo_path = os.path.join(clone_dir, repo_name)

    # Remove the directory if it exists.
    if os.path.exists(repo_path):
        shutil.rmtree(repo_path, ignore_errors=True)

    # Clone the repository.
    subprocess.run(["git", "clone", repo_url, repo_path])

    # Return the cloned repository path.
    return repo_path
