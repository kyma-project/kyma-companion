import os
import subprocess
from logging import Formatter, Logger, StreamHandler, getLogger


def get_logger(name: str, log_level: str) -> Logger:
    """Returns a preconfigured logger instance."""
    logger = getLogger(name)
    formatter = Formatter(
        fmt="{asctime} - {levelname} - {name} : {message}",
        style="{",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler = StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.setLevel(log_level)
    return logger


def clone_repo(repo_url: str, clone_dir: str) -> str:
    """Clones the git repository and returns the path."""
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    repo_path = os.path.join(clone_dir, repo_name)
    if not os.path.exists(repo_path):
        subprocess.run(["git", "clone", repo_url, repo_path])
    return repo_path
