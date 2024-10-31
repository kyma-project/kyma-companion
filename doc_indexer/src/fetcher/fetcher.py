import os
import shutil

from fetcher.scroller import Scroller
from fetcher.source import DocumentsSource, SourceType, get_documents_sources

from utils.logging import get_logger
from utils.utils import clone_repo

logger = get_logger(__name__)


class DocumentsFetcher:
    """Class to fetch the documents from the specified sources."""

    output_dir: str
    tmp_dir: str
    sources: list[DocumentsSource]

    def __init__(self, source_file: str, output_dir: str, tmp_dir: str) -> None:
        """Initializes the DocumentsFetcher class."""
        self.output_dir = output_dir
        self.tmp_dir = tmp_dir

        # delete the directories if they exist
        shutil.rmtree(self.output_dir, ignore_errors=True)
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

        # read the documents sources from the json file.
        self.sources = get_documents_sources(source_file)

        # Create directories if they don't exist
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.tmp_dir, exist_ok=True)

    def fetch_documents(self, source: DocumentsSource) -> None:
        """Fetch the documents from the source."""
        logger.info(f"******* Fetching documents for: {source.name}")

        if source.source_type == SourceType.GITHUB:
            logger.debug(f"Cloning repository: {source.url}")
            # clone the git repository.
            repo_dir = clone_repo(source.url, self.tmp_dir)
        else:
            raise ValueError(f"unsupported source_type: {source.source_type}")

        module_output_dir = os.path.join(self.output_dir, source.name)
        logger.debug(f"Creating a temporary directory: {module_output_dir}")
        os.makedirs(module_output_dir, exist_ok=True)

        # extract markdown files
        try:
            scroller = Scroller(repo_dir, module_output_dir, source)
            scroller.scroll()
        except Exception as e:
            logger.error(
                f"Error while scrolling documents for: {source.name}: {str(e)}"
            )
            raise e
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
        shutil.rmtree(self.tmp_dir, ignore_errors=False)
