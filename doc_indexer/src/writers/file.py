import json

from langchain_core.documents import Document
from writers.base import RunDescriptor

from utils.logging import get_logger

logger = get_logger(__name__)


class FileWriter:
    """Writes chunks and vectors into one JSON file.

    POC: all chunks are buffered in memory until commit() (a 100 MB index is held once as Python objects,
    which is acceptable here). A streaming writer would be needed for much larger indexes.
    """

    needs_embeddings = True

    def __init__(self, path: str):
        # may contain "{run_id}", substituted in begin()
        self.path = path
        self._run: RunDescriptor | None = None
        self._chunks: list[dict] = []

    def begin(self, run: RunDescriptor) -> None:
        """Prepare the output for a new run."""
        self._run = run
        self._chunks = []
        self.path = self.path.replace("{run_id}", run.run_id)

    def write(self, chunks: list[Document], vectors: list[list[float]]) -> None:
        """Write one batch of chunks (with vectors if the writer needs them)."""
        for chunk, vector in zip(chunks, vectors, strict=True):
            self._chunks.append({"content": chunk.page_content, "metadata": chunk.metadata, "embedding": vector})

    def commit(self) -> None:
        """Make the written run visible."""
        assert self._run is not None
        with open(self.path, "w", encoding="utf-8") as out:
            json.dump({"run": self._run.to_dict(), "chunks": self._chunks}, out)
        logger.info(f"Stored {len(self._chunks)} chunks in file: {self.path}")

    def abort(self) -> None:
        """Discard everything written by this run."""
        self._chunks = []
