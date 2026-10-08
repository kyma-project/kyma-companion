import os
import secrets
import subprocess
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
    # Optional additional keys that only the file writer stores (e.g. "exported_from"). Not written to Postgres.
    extra: dict[str, Any] = field(default_factory=dict)
    # Which indexer code built the run: INDEXER_VERSION or GITHUB_SHA from the environment, else the git commit.
    indexer_version: str = field(default_factory=lambda: detect_indexer_version())

    def to_dict(self) -> dict[str, Any]:
        """Return the descriptor as a plain dict (extra keys merged at top level, only if present)."""
        data = asdict(self)
        data.pop("extra")
        data.update(self.extra)
        return data


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


def detect_indexer_version() -> str:
    """Return the indexer version: INDEXER_VERSION, else GITHUB_SHA, else the short git commit, else "unknown"."""
    for key in ("INDEXER_VERSION", "GITHUB_SHA"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    try:
        out = subprocess.run(  # noqa: S603, S607 - fixed argv, no shell
            ["git", "rev-parse", "--short=12", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=os.path.dirname(os.path.abspath(__file__)),
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"
