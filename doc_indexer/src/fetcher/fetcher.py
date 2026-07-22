import os
import re
import shutil

from fetcher.scroller import Scroller
from fetcher.source import DocumentsSource, SourceType, get_documents_sources

from utils.logging import get_logger
from utils.utils import download_repo

logger = get_logger(__name__)


def _empty_dir(path: str) -> None:
    """Remove everything *inside* a directory, leaving the directory itself.

    Deleting the directory itself would require write access to its parent,
    which the non-root container user does not have for /app-rooted paths
    (see the doc_indexer Dockerfile). Emptying the contents only needs write
    access to the directory, which the user does have.
    """
    if not os.path.isdir(path):
        return
    for entry in os.scandir(path):
        if entry.is_dir(follow_symlinks=False):
            shutil.rmtree(entry.path, ignore_errors=True)
        else:
            os.remove(entry.path)


class DocumentsFetcher:
    """Class to fetch the documents from the specified sources"""

    output_dir: str
    tmp_dir: str
    sources: list[DocumentsSource]

    def __init__(self, source_file: str, output_dir: str, tmp_dir: str) -> None:
        """Initializes the DocumentsFetcher class."""
        self.output_dir = output_dir
        self.tmp_dir = tmp_dir

        # Create the directories if they don't exist, then clear their contents.
        # Emptying (rather than removing) the dirs keeps them usable by a non-root
        # user that lacks write access to the parent directory.
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.tmp_dir, exist_ok=True)
        _empty_dir(self.output_dir)
        _empty_dir(self.tmp_dir)

        # read the documents sources from the json file.
        self.sources = get_documents_sources(source_file)

    def fetch_documents(self, source: DocumentsSource) -> None:
        """Fetch the documents from the source."""
        logger.info("Fetching documents", extra={"source": source.name, "url": source.url})

        if not re.fullmatch(r"[A-Za-z0-9_-]+", source.name):
            raise ValueError(f"Invalid source name: {source.name}")

        if source.source_type == SourceType.GITHUB:
            logger.debug(f"Downloading repository: {source.url}")
            # download and extract the repository tarball (no git required).
            repo_dir = download_repo(source.url, self.tmp_dir)
        else:
            raise ValueError(f"unsupported source_type: {source.source_type}")

        module_output_dir = os.path.join(self.output_dir, source.name)
        logger.debug(f"Creating a temporary directory: {module_output_dir}")
        os.makedirs(module_output_dir, exist_ok=True)

        # extract markdown files
        try:
            scroller = Scroller(repo_dir, module_output_dir, source)
            scroller.scroll()
        except Exception:
            logger.exception(f"Error while scrolling documents for: {source.name}")
            raise
        finally:
            # delete the directories if they exist
            logger.debug(f"Deleting the temporary directory: {repo_dir}")
            shutil.rmtree(repo_dir, ignore_errors=False)

    def run(self) -> None:
        """Fetch the documents from all the sources."""
        for source in self.sources:
            self.fetch_documents(source)
        logger.info("Documents fetched successfully from all sources!")

        # clean the temporary files.
        self.clean()

    def clean(self) -> None:
        """Clean the temporary files."""
        _empty_dir(self.tmp_dir)
