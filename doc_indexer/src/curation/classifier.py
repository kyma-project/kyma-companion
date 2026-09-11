"""LLM-based classifier for residue documents using structured output."""

import json
from typing import Any

from curation.models import CandidateDoc, ClassificationResult, CuratorConfig
from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
from gen_ai_hub.proxy.langchain import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from utils.logging import get_logger

logger = get_logger(__name__)

_BATCH_SIZE = 20

_SYSTEM_PROMPT = """\
You are a documentation curator for Kyma and SAP BTP Kyma runtime.

Classification rules:
- INCLUDE: User-facing Kyma or SAP BTP Kyma runtime documentation (tutorials, how-to guides,
  reference docs, overviews, glossaries, getting-started content).
- EXCLUDE: Contributor documentation, Architecture Decision Records (ADRs), CI/CD scripts,
  benchmark results, internal design material, developer setup guides, CHANGELOG files,
  and any content not intended for end users of Kyma.
- UNSURE: Anything that does not clearly fall into include or exclude.

Respond with a JSON array. Each element must correspond to exactly one input document
(in the same order) and must have these fields:
- decision: "include" | "exclude" | "unsure"
- doc_type: short string describing the document type (e.g. "tutorial", "reference", "adr"), or null
- module: Kyma module name if identifiable, otherwise null
- confidence: float between 0.0 and 1.0
- rationale: one sentence explaining the decision
"""

_CANDIDATE_TEMPLATE = """\
--- Document {index} ---
repo: {repo}
path: {path}
h1: {h1}
directory: {directory}
residue_reason: {residue_reason}
content_excerpt:
{excerpt}
"""


class _SingleDecision(BaseModel):
    """Structured output schema for one document decision."""

    decision: str = Field(description="include, exclude, or unsure")
    doc_type: str | None = Field(default=None, description="Document type label")
    module: str | None = Field(default=None, description="Kyma module name")
    confidence: float = Field(description="Confidence in [0, 1]")
    rationale: str = Field(description="One-sentence rationale")


def _build_user_message(batch: list[CandidateDoc]) -> str:
    """Build the user message body for a batch of candidates.

    Args:
        batch: Candidate documents to include in the prompt.

    Returns:
        Formatted user message text.
    """
    parts = []
    for i, doc in enumerate(batch, start=1):
        parts.append(
            _CANDIDATE_TEMPLATE.format(
                index=i,
                repo=doc.repo,
                path=doc.path,
                h1=doc.h1 or "(none)",
                directory=doc.directory,
                residue_reason=doc.residue_reason,
                excerpt=doc.excerpt,
            )
        )
    parts.append(f"\nReturn a JSON array with exactly {len(batch)} elements, one per document above.")
    return "\n".join(parts)


def _parse_decisions(raw: str, batch: list[CandidateDoc]) -> list[_SingleDecision]:
    """Parse the raw JSON string from the model into a list of decisions.

    Falls back to *len(batch)* unsure decisions on any parse error.

    Args:
        raw: Raw string response from the model.
        batch: The batch being processed (used for length check).

    Returns:
        List of :class:`_SingleDecision` instances, one per candidate.
    """
    try:
        data = json.loads(raw)
        if not isinstance(data, list):
            raise ValueError("expected a JSON array at top level")
        return [_SingleDecision(**item) for item in data]
    except Exception as exc:
        logger.warning(f"classifier: failed to parse model response: {exc!r} -- marking batch as unsure")
        return [
            _SingleDecision(decision="unsure", doc_type=None, module=None, confidence=0.0, rationale="parse error")
            for _ in batch
        ]


def _create_llm(config: CuratorConfig) -> Any:
    """Instantiate the ChatOpenAI LLM from the SAP gen-ai-hub proxy.

    Args:
        config: Curator configuration.

    Returns:
        A ChatOpenAI instance.
    """
    proxy_client = get_proxy_client("gen-ai-hub")
    kwargs: dict[str, Any] = {
        "proxy_client": proxy_client,
        "temperature": 0,
    }
    if config.model_name:
        kwargs["deployment_id"] = config.model_name
    return ChatOpenAI(**kwargs)


def _classify_batch(
    batch: list[CandidateDoc],
    llm: Any,
) -> list[ClassificationResult]:
    """Classify a single batch of candidate documents.

    On any model call failure, all candidates in the batch are marked as
    ``decision='unsure'`` with a descriptive rationale; no exception is raised.

    Args:
        batch: Up to *_BATCH_SIZE* candidate documents.
        llm: LangChain chat model instance.

    Returns:
        List of :class:`ClassificationResult` objects, one per candidate.
    """
    user_text = _build_user_message(batch)
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=user_text),
    ]

    try:
        response = llm.invoke(messages)
        raw = response.content if hasattr(response, "content") else str(response)
        decisions = _parse_decisions(raw, batch)
    except Exception as exc:
        err_msg = f"classifier error: {exc!r}"
        logger.warning(f"classifier: model call failed: {err_msg}")
        decisions = [
            _SingleDecision(decision="unsure", doc_type=None, module=None, confidence=0.0, rationale=err_msg)
            for _ in batch
        ]

    # Zip decisions with candidates -- always emit one result per candidate
    results: list[ClassificationResult] = []
    for i, candidate in enumerate(batch):
        if i < len(decisions):
            dec = decisions[i]
        else:
            dec = _SingleDecision(
                decision="unsure", doc_type=None, module=None, confidence=0.0, rationale="no decision returned"
            )
        try:
            confidence = max(0.0, min(1.0, float(dec.confidence)))
        except (TypeError, ValueError):
            confidence = 0.0
        results.append(
            ClassificationResult(
                candidate=candidate,
                decision=dec.decision if dec.decision in ("include", "exclude", "unsure") else "unsure",
                doc_type=dec.doc_type,
                module=dec.module,
                confidence=confidence,
                rationale=dec.rationale,
                decided_by="agent",
            )
        )
    return results


def classify_residue(
    candidates: list[CandidateDoc],
    config: CuratorConfig,
) -> list[ClassificationResult]:
    """Classify a list of residue candidate documents using an LLM.

    Candidates are processed in batches of :data:`_BATCH_SIZE`.  Any batch
    that fails (network error, model error, parse error) is returned with
    ``decision='unsure'`` rather than raising an exception.

    Args:
        candidates: Documents to classify.
        config: Curator configuration (model name, etc.).

    Returns:
        List of :class:`ClassificationResult` objects in the same order as
        *candidates*.
    """
    if not candidates:
        return []

    llm = _create_llm(config)

    all_results: list[ClassificationResult] = []
    num_batches = (len(candidates) + _BATCH_SIZE - 1) // _BATCH_SIZE

    for batch_idx in range(num_batches):
        start = batch_idx * _BATCH_SIZE
        batch = candidates[start : start + _BATCH_SIZE]
        logger.info(f"classifier: processing batch {batch_idx + 1}/{num_batches} ({len(batch)} candidates)")
        results = _classify_batch(batch, llm)
        all_results.extend(results)

    logger.info(f"classifier: classified {len(all_results)} candidates in {num_batches} batch(es)")
    return all_results
