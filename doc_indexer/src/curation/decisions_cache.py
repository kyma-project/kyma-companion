"""Persistent JSONL cache for curator classification decisions."""

import dataclasses
import json
import os
from typing import Any

from curation.models import CandidateDoc, ClassificationResult

from utils.logging import get_logger

logger = get_logger(__name__)


def _result_to_dict(result: ClassificationResult) -> dict[str, Any]:
    """Serialise a :class:`ClassificationResult` to a JSON-compatible dict.

    Args:
        result: The classification result to serialise.

    Returns:
        Dictionary suitable for ``json.dumps``.
    """
    d = dataclasses.asdict(result)
    return d


def _result_from_dict(d: dict[str, Any]) -> ClassificationResult:
    """Deserialise a :class:`ClassificationResult` from a dict.

    Args:
        d: Dictionary as produced by :func:`_result_to_dict`.

    Returns:
        Reconstructed :class:`ClassificationResult`.
    """
    candidate = CandidateDoc(**d["candidate"])
    return ClassificationResult(
        candidate=candidate,
        decision=d["decision"],
        doc_type=d.get("doc_type"),
        module=d.get("module"),
        confidence=d["confidence"],
        rationale=d["rationale"],
        decided_by=d.get("decided_by", "agent"),
    )


def _cache_key(repo: str, path: str, content_hash: str) -> str:
    """Return the string key used to identify a cached decision.

    Args:
        repo: Repository name.
        path: File path relative to the repo root.
        content_hash: SHA-256 hex digest of the file content.

    Returns:
        Composite cache key string.
    """
    return f"{repo}::{path}::{content_hash}"


class DecisionsCache:
    """JSONL-backed cache of classification decisions.

    Each line in the backing file is a JSON object representing one
    :class:`ClassificationResult`.  The cache is keyed by
    ``f"{repo}::{path}::{content_hash}"`` so that a file whose content
    has changed since last classification is not considered cached.

    Args:
        decisions_file: Absolute or relative path to the JSONL file.
    """

    def __init__(self, decisions_file: str) -> None:
        self._path = decisions_file
        self._cache: dict[str, ClassificationResult] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> dict[str, ClassificationResult]:
        """Load (or reload) the cache from disk.

        Missing file is treated as an empty cache (not an error).

        Returns:
            Mapping from cache key to :class:`ClassificationResult`.
        """
        self._cache = {}
        if not os.path.exists(self._path):
            self._loaded = True
            return self._cache

        skipped = 0
        with open(self._path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    result = _result_from_dict(d)
                    key = _cache_key(result.candidate.repo, result.candidate.path, result.candidate.content_hash)
                    self._cache[key] = result
                except Exception:
                    logger.warning(f"decisions cache: skipping malformed line {lineno} in '{self._path}'")
                    skipped += 1

        self._loaded = True
        logger.info(f"decisions cache: loaded {len(self._cache)} entries from '{self._path}' ({skipped} skipped)")
        return self._cache

    def save(self, results: list[ClassificationResult]) -> None:
        """Append new (uncached) entries to the JSONL file.

        Existing entries are never rewritten.  Only results whose cache key
        is not already present in the in-memory cache are written.

        Args:
            results: Classification results to persist.
        """
        if not self._loaded:
            self.load()

        new_entries: list[ClassificationResult] = []
        for result in results:
            key = _cache_key(result.candidate.repo, result.candidate.path, result.candidate.content_hash)
            if key not in self._cache:
                new_entries.append(result)
                self._cache[key] = result

        if not new_entries:
            return

        os.makedirs(os.path.dirname(os.path.abspath(self._path)), exist_ok=True)
        with open(self._path, "a", encoding="utf-8") as fh:
            for result in new_entries:
                fh.write(json.dumps(_result_to_dict(result)) + "\n")

        logger.info(f"decisions cache: appended {len(new_entries)} new entries to '{self._path}'")

    def is_cached(self, candidate: CandidateDoc) -> bool:
        """Return True if a decision for *candidate* is already in the cache.

        Args:
            candidate: The candidate document to check.

        Returns:
            True when a cache entry exists for the candidate's repo/path/hash.
        """
        if not self._loaded:
            self.load()
        key = _cache_key(candidate.repo, candidate.path, candidate.content_hash)
        return key in self._cache

    def get(self, candidate: CandidateDoc) -> ClassificationResult | None:
        """Return the cached decision for *candidate*, or None.

        Args:
            candidate: The candidate document to look up.

        Returns:
            The cached :class:`ClassificationResult`, or None if not present.
        """
        if not self._loaded:
            self.load()
        key = _cache_key(candidate.repo, candidate.path, candidate.content_hash)
        return self._cache.get(key)
