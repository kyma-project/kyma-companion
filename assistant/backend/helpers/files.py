import os
from pathlib import Path
from typing import List


def load_markdown_files(directory_path: str) -> List[str]:
    """Loads all markdown files (including those in subdirectories) from the specified directory.

    Args:
        directory_path (str): The path to the directory containing markdown files.

    Returns:
        List[str]: A list where each element is the content of a single markdown file.
    """
    markdown_files = []

    for root, _, files in os.walk(directory_path):
        for file in files:
            if file.endswith(".md"):
                file_path = os.path.join(root, file)
                with open(file_path, "r") as f:
                    content = f.read()
                    markdown_files.append(content)

    return markdown_files
