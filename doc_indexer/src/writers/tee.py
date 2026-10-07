from langchain_core.documents import Document
from writers.base import RunDescriptor, Writer

from utils.logging import get_logger

logger = get_logger(__name__)


class TeeWriter:
    """Fans every call out to several writers, in order."""

    def __init__(self, writers: list[Writer]):
        if not writers:
            raise ValueError("TeeWriter needs at least one writer.")
        self.writers = writers
        self.needs_embeddings = any(w.needs_embeddings for w in writers)
        self._finished: set[int] = set()  # indexes of writers that are committed or aborted

    def begin(self, run: RunDescriptor) -> None:
        """Prepare all outputs for a new run."""
        self._finished = set()
        for w in self.writers:
            w.begin(run)

    def write(self, chunks: list[Document], vectors: list[list[float]]) -> None:
        """Write one batch to every writer (HanaWriter uses passed vectors instead of embedding again)."""
        for w in self.writers:
            w.write(chunks, vectors)

    def commit(self) -> None:
        """Commit in order; if one fails, abort it and all remaining uncommitted writers, then re-raise."""
        for i, w in enumerate(self.writers):
            try:
                w.commit()
            except Exception:
                logger.exception(f"Commit failed for writer {type(w).__name__}; aborting the remaining writers")
                self.abort()
                raise
            self._finished.add(i)

    def abort(self) -> None:
        """Abort all writers that are not committed yet."""
        for i, w in enumerate(self.writers):
            if i in self._finished:
                continue
            self._finished.add(i)
            try:
                w.abort()
            except Exception:
                logger.exception(f"Abort failed for writer {type(w).__name__}")
