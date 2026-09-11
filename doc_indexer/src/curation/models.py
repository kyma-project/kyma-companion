"""Data models shared across the curation package."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass
class CandidateDoc:
    """A document candidate for curation classification.

    Attributes:
        repo: Repository name (matches 'name' field in docs_sources.json).
        path: Relative path of the file within the repo.
        h1: First H1 heading found in the file, or None if absent.
        excerpt: First ~600 tokens of content, used as input to the classifier.
        directory: Absolute or relative path to the directory containing the file.
        residue_reason: Why this file is considered residue.
        content_hash: SHA-256 hex digest of the full file content.
    """

    repo: str
    path: str
    h1: str | None
    excerpt: str
    directory: str
    residue_reason: str
    content_hash: str


@dataclass
class ClassificationResult:
    """The classifier's decision for a single candidate document.

    Attributes:
        candidate: The document that was classified.
        decision: One of 'include', 'exclude', or 'unsure'.
        doc_type: Optional free-text label for the document type (e.g. 'tutorial', 'reference').
        module: Optional Kyma module name inferred from the document.
        confidence: Confidence score in [0.0, 1.0].
        rationale: Brief explanation of the decision.
        decided_by: Who made the decision (default: 'agent').
    """

    candidate: CandidateDoc
    decision: Literal["include", "exclude", "unsure"]
    doc_type: str | None
    module: str | None
    confidence: float
    rationale: str
    decided_by: str = "agent"


@dataclass
class CuratorConfig:
    """Configuration for the curator.

    Attributes:
        residue_to_agent: When True, uncached residue is sent to the classifier LLM.
        decisions_file: Path (relative to docs_path) for the JSONL decisions cache.
        model_name: SAP AI Core model name to use.  None = use the default mini model
            configured in settings (CURATOR_MODEL_NAME env var).
    """

    residue_to_agent: bool = False
    decisions_file: str = "curation/decisions.jsonl"
    model_name: str | None = field(default=None)
