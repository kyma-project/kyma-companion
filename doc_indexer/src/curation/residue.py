"""Residue detection: find .md files under docs_path that are not covered by include_files patterns."""

import fnmatch
import hashlib
import os
import re

import tiktoken
from curation.models import CandidateDoc

from utils.logging import get_logger

logger = get_logger(__name__)

_EXCERPT_TOKEN_LIMIT = 600
_ENCODING = tiktoken.get_encoding("cl100k_base")


def _truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Return at most *max_tokens* tokens of *text*, decoded back to a string.

    Args:
        text: Input text to truncate.
        max_tokens: Maximum number of tokens to keep.

    Returns:
        Truncated text.
    """
    tokens = _ENCODING.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return _ENCODING.decode(tokens[:max_tokens])


def _extract_h1(content: str) -> str | None:
    """Return the first H1 heading from Markdown content, or None.

    Args:
        content: Raw Markdown content.

    Returns:
        The heading text (without the leading '# '), or None.
    """
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    return match.group(1).strip() if match else None


def _content_hash(content: str) -> str:
    """Return SHA-256 hex digest of the given string content.

    Args:
        content: Raw file content.

    Returns:
        Hex digest string.
    """
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()


def _matches_any_pattern(rel_path: str, patterns: list[str]) -> bool:
    """Return True if *rel_path* matches at least one glob pattern.

    The patterns use the same glob syntax as docs_sources.json ``include_files``
    entries (e.g. ``docs/user/*``, ``README.md``).  We normalise separators and:

    - Try a plain ``fnmatch`` against the full path.
    - For patterns ending in ``/*``, also treat them as prefix matches so that
      files nested deeper (e.g. ``docs/user/sub/page.md``) are covered.
    - For patterns without a ``/``, also match against the basename alone so
      that ``README.md`` matches at any depth.

    Args:
        rel_path: Path relative to the repo root (with forward slashes).
        patterns: List of glob patterns from the source entry.

    Returns:
        True if at least one pattern matches.
    """
    normalised = rel_path.replace("\\", "/")
    for pattern in patterns:
        pattern = pattern.replace("\\", "/")
        if fnmatch.fnmatch(normalised, pattern):
            return True
        # For patterns like "docs/user/*", also match deeper paths like
        # "docs/user/sub/page.md" by treating the prefix as a directory match.
        if pattern.endswith("/*"):
            prefix = pattern[:-1]  # e.g. "docs/user/"
            if normalised.startswith(prefix):
                return True
        # Also match basename for single-level patterns like "README.md"
        if "/" not in pattern and fnmatch.fnmatch(os.path.basename(normalised), pattern):
            return True
    return False


def find_residue(docs_path: str, sources: list[dict]) -> list[CandidateDoc]:
    """Walk *docs_path* and return all .md files that are residue.

    A file is considered residue when:
    - Its containing module directory has no entry in *sources*
      (``residue_reason='new_repo'``), or
    - It does not match any ``include_files`` pattern for its module
      (``residue_reason='not_in_include_patterns'``).

    Args:
        docs_path: Root directory containing per-module sub-directories
            (e.g. ``doc_indexer/data``).
        sources: Parsed contents of ``docs_sources.json`` -- a list of dicts
            each with at least ``name`` and ``include_files`` keys.

    Returns:
        List of :class:`CandidateDoc` objects for residue files.
    """
    if not os.path.isdir(docs_path):
        logger.info(f"docs_path '{docs_path}' does not exist -- returning empty residue list")
        return []

    # Build a lookup: module_name -> include_files patterns
    sources_by_name: dict[str, list[str]] = {
        entry["name"]: entry.get("include_files", []) for entry in sources if "name" in entry
    }

    candidates: list[CandidateDoc] = []

    for module_dir in sorted(os.listdir(docs_path)):
        module_path = os.path.join(docs_path, module_dir)
        if not os.path.isdir(module_path):
            continue

        is_known = module_dir in sources_by_name
        include_patterns = sources_by_name.get(module_dir, [])

        for root, _dirs, files in os.walk(module_path):
            for filename in sorted(files):
                if not filename.endswith(".md"):
                    continue

                abs_path = os.path.join(root, filename)

                # Compute repo-relative path (relative to module directory)
                rel_to_module = os.path.relpath(abs_path, module_path).replace("\\", "/")

                if not is_known:
                    residue_reason = "new_repo"
                elif _matches_any_pattern(rel_to_module, include_patterns):
                    # File is explicitly included -- not residue
                    continue
                else:
                    residue_reason = "not_in_include_patterns"

                try:
                    with open(abs_path, encoding="utf-8", errors="replace") as fh:
                        content = fh.read()
                except OSError:
                    logger.warning(f"Could not read '{abs_path}' -- skipping")
                    continue

                candidates.append(
                    CandidateDoc(
                        repo=module_dir,
                        path=rel_to_module,
                        h1=_extract_h1(content),
                        excerpt=_truncate_to_tokens(content, _EXCERPT_TOKEN_LIMIT),
                        directory=root,
                        residue_reason=residue_reason,
                        content_hash=_content_hash(content),
                    )
                )

    logger.info(f"find_residue: found {len(candidates)} residue file(s) under '{docs_path}'")
    return candidates
