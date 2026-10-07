import secrets
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from langchain_core.documents import Document


def new_run_id() -> str:
    """Return a run id like 20261007143012_a1f3c9 (UTC timestamp + 6 hex chars, only [a-z0-9_])."""
    return f"{time.strftime('%Y%m%d%H%M%S', time.gmtime())}_{secrets.token_hex(3)}"


@dataclass
class RunDescriptor:
    """Describes one indexing run."""

    run_id: str
    embedding_model: str
    dimensions: int
    sources: dict[str, Any] = field(default_factory=dict)  # fetch manifest.json content

    def to_dict(self) -> dict[str, Any]:
        """Return the descriptor as a plain dict."""
        return asdict(self)


class Writer(Protocol):
    """Output of the indexer. Call order: begin, write (n times), commit. abort on any error."""

    # True if the indexer must embed the chunks itself and pass the vectors to write().
    needs_embeddings: bool

    def begin(self, run: RunDescriptor) -> None:
        """Prepare the output for a new run."""
        ...

    def write(self, chunks: list[Document], vectors: list[list[float]]) -> None:
        """Write one batch of chunks (with vectors if the writer needs them)."""
        ...

    def commit(self) -> None:
        """Make the written run visible."""
        ...

    def abort(self) -> None:
        """Discard everything written by this run."""
        ...
