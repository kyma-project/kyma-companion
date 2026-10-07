from langchain_core.documents import Document
from langchain_hana import HanaDB
from writers.base import RunDescriptor

from utils.logging import get_logger

logger = get_logger(__name__)


class HanaWriter:
    """Existing behaviour: delete all rows, then add documents. HanaDB embeds the chunks itself."""

    needs_embeddings = False

    def __init__(self, db: HanaDB):
        self.db = db

    def begin(self, run: RunDescriptor) -> None:
        """Prepare the output for a new run."""
        logger.info("Deleting existing index in HanaDB...")
        try:
            self.db.delete(filter={})
        except Exception:
            logger.exception("Error while deleting existing documents in HanaDB.")
            raise
        logger.info("Successfully deleted existing documents in HanaDB.")

    def write(self, chunks: list[Document], vectors: list[list[float]]) -> None:
        """Write one batch of chunks (with vectors if the writer needs them)."""
        self.db.add_documents(chunks)

    def commit(self) -> None:
        """Make the written run visible."""
        return None

    def abort(self) -> None:
        """Discard everything written by this run."""
        return None
