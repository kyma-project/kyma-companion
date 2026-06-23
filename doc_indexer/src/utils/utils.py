import os
import re
import shutil
import subprocess

from utils.logging import get_logger

logger = get_logger(__name__)


def clone_repo(repo_url: str, clone_dir: str) -> str:
    """Clones the git repository and returns the path."""
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    repo_path = os.path.join(clone_dir, repo_name)

    if os.path.exists(repo_path):
        shutil.rmtree(repo_path, ignore_errors=True)

    logger.info("Cloning repository", extra={"url": repo_url, "dest": repo_path})
    result = subprocess.run(["git", "clone", repo_url, repo_path])
    if result.returncode != 0:
        raise RuntimeError(f"git clone failed for {repo_url} (exit {result.returncode})")
    logger.info("Repository cloned successfully", extra={"url": repo_url, "dest": repo_path})

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
