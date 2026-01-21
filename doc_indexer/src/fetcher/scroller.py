import fnmatch
import os
import shutil

from fetcher.source import DocumentsSource

from utils.logging import get_logger

logger = get_logger(__name__)


class Scroller:
    """Scroller class to scroll through the files and save the required files."""

    dir_path: str
    output_dir: str
    source: DocumentsSource

    def __init__(self, dir_path: str, output_dir: str, source: DocumentsSource) -> None:
        """Initializes the Scroller class."""
        self.dir_path = dir_path
        self.output_dir = output_dir
        self.source = source

    def _save_file(self, file_dir: str, file_name: str) -> None:
        """Saves the file to the output directory."""
        source_file_path = os.path.join(self.dir_path, file_dir, file_name)

        target_dir = os.path.join(self.output_dir, file_dir)
        os.makedirs(target_dir, exist_ok=True)

        shutil.copy(source_file_path, target_dir)
        logger.info(f"Saved file {source_file_path} to {target_dir}")

    def _should_exclude_file(self, file_path: str) -> bool:
        """Check if the file should be excluded."""
        if self.source.exclude_files is None:
            raise ValueError("exclude_files is None.")
        return any(fnmatch.fnmatch(file_path, pattern) for pattern in self.source.exclude_files)

    def _should_include_file(self, file_path: str) -> bool:
        """Check if the file should be included."""
        if self.source.include_files is None:
            raise ValueError("include_files is None.")
        return any(fnmatch.fnmatch(file_path, pattern) for pattern in self.source.include_files)

    def scroll(self) -> None:
        """Scroll through the files and save the required files."""
        for file_dir, _, files in os.walk(self.dir_path):
            relative_dir = file_dir.removeprefix(self.dir_path).lstrip("/")
            for file_name in files:
                file_path = os.path.join(relative_dir, file_name)

                # skip if file type is not allowed.
                if file_name.split(".")[-1] not in self.source.filter_file_types:
                    logger.debug(f"skipping file {file_path} because file type not allowed.")
                    continue

                if self.source.exclude_files is not None and self._should_exclude_file(file_path):
                    logger.debug(f"skipping file {file_path} because file is in exclude_files list.")
                    continue

                # if include_files is None, then we include all the files.
                # but if include_files is not None, then we only include the files that are in the include_files list.
                if self.source.include_files is not None:
                    if self._should_include_file(file_path):
                        self._save_file(relative_dir, file_name)
                    else:
                        logger.debug(f"skipping file {file_path} because file is not in include_files list.")
                else:
                    self._save_file(relative_dir, file_name)
