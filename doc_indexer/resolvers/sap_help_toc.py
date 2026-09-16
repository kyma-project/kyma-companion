#!/usr/bin/env python3
"""External pinakes resolver (SPEC §3) for the SAP Help Portal table of contents.

Reimplements ``resolve_sap_help_toc`` from ``doc_indexer/src/fetcher/resolvers.py`` as a
dependency-free script pinakes can run directly against a checkout, without importing anything
from the ``doc_indexer`` package (pinakes ships this file standalone).

The table of contents (``docs/index.md`` by default) is a nested Markdown list. An entry whose
title matches ``title_match`` (default ``(?i)kyma``) selects itself and every entry nested below
it, until a sibling or ancestor line ends the subtree. Pages can appear under several branches;
the first matching branch wins and supplies the section breadcrumb.

Every other Markdown file under the table of contents' directory is emitted as an unselected
candidate too, so pinakes can apply ``resolver.residue_mention`` against the actual file text
(SPEC §3) and report only the ones that mention the match term as residue.

Usage: ``sap_help_toc.py [TOC_PATH] [TITLE_MATCH]``, run with cwd = the repository checkout.
"""

from __future__ import annotations

import json
import os
import re
import sys

_TOC_LINE_RE = re.compile(r"^(?P<indent>\s*)-\s+\[(?P<title>[^\]]+)\]\((?P<link>[^)]+)\)")

_TROUBLESHOOTING_RE = re.compile(
    r"troubleshoot|diagnos|error|issue|fail|not (?:working|found|ready|delivered)|cannot|can't|unable|"
    r"pending|refused|forbidden|denied|missing|incompatible|conflict|reverting|recover",
    re.IGNORECASE,
)
_TUTORIAL_RE = re.compile(
    r"^(?:tutorial|getting started|get started|create|creating|configure|configuring|enable|enabling|expose|"
    r"exposing|deploy|deploying|set up|setting up|add|adding|manage|managing|migrate|migrating|use|using|send|"
    r"sending|subscribe|install|installing|assign|connect|integrate|update|delete|retrieve|access|run|running|"
    r"customize|inject|override|log into|collect|restart|choose|switch|activate|change|generate|build|test|"
    r"upgrade|provision|register|secure|scale|monitor|publish|trigger|bind|mount|migrat|register)\b",
    re.IGNORECASE,
)
_REFERENCE_RE = re.compile(
    r"reference|parameter|specification|\bapi\b|\bcr\b|custom resource|resources?$|architecture|glossary|"
    r"metrics|limitations|schema|presets|configmap|rbac|gen-docs|commands?$|\bkyma (?:alpha|module|app)\b",
    re.IGNORECASE,
)
_RELEASE_RE = re.compile(r"release notes?|what's new|changelog", re.IGNORECASE)


def classify_doc_type(title: str, ancestors: list[str]) -> str:
    """Return a coarse ``doc_type`` for a page from its title and section titles.

    Args:
        title: The page title.
        ancestors: Section titles from the root down to the page's parent, nearest last.

    Returns:
        One of ``concept``, ``tutorial``, ``reference``, ``troubleshooting``, ``release-notes``.
    """
    for text in [*reversed(ancestors), title]:
        if _RELEASE_RE.search(text):
            return "release-notes"
        if _TROUBLESHOOTING_RE.search(text):
            return "troubleshooting"
        if re.search(r"tutorial", text, re.IGNORECASE):
            return "tutorial"
        if re.search(r"technical reference|^resources$|custom resources?$", text, re.IGNORECASE):
            return "reference"
    if _TUTORIAL_RE.search(title):
        return "tutorial"
    if _REFERENCE_RE.search(title):
        return "reference"
    return "concept"


def resolve_link(base_dir: str, link: str) -> str | None:
    """Map a table-of-contents link to an existing Markdown file, repository-relative.

    Args:
        base_dir: Directory the link is relative to (the TOC file's own directory).
        link: The raw link target, possibly carrying an anchor.

    Returns:
        The resolved repository-relative path, or ``None`` when no file matches.
    """
    target = link.split("#", 1)[0].strip().removeprefix("./")
    if not target:
        return None
    candidates = [target] if target.endswith(".md") else [f"{target}.md", f"{target}/README.md", target]
    for candidate in candidates:
        rel = os.path.normpath(os.path.join(base_dir, candidate))
        if rel.startswith("..") or not rel.endswith(".md"):
            continue
        if os.path.isfile(rel):
            return rel
    return None


def markdown_files(root: str) -> list[str]:
    """Return every ``.md`` path under *root*, relative to the repository root, sorted."""
    found: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            if filename.endswith(".md"):
                found.append(os.path.relpath(os.path.join(dirpath, filename), "."))
    return sorted(found)


_ARGV_TOC_PATH = 1
_ARGV_TITLE_MATCH = 2


def parse_args(argv: list[str]) -> tuple[str, str]:
    """Return ``(toc_path, title_match)`` from CLI arguments, applying the documented defaults."""
    toc_path = argv[_ARGV_TOC_PATH] if len(argv) > _ARGV_TOC_PATH else "docs/index.md"
    title_match = argv[_ARGV_TITLE_MATCH] if len(argv) > _ARGV_TITLE_MATCH else "(?i)kyma"
    return toc_path, title_match


def select_toc_pages(lines: list[str], base_dir: str, pattern: re.Pattern[str]) -> dict[str, tuple[str, str, str]]:
    """Walk the table-of-contents lines, returning selected pages as path -> (title, doc_type, section)."""
    selected: dict[str, tuple[str, str, str]] = {}
    ancestors: list[tuple[int, str]] = []  # (indent, title)
    selected_depth: int | None = None
    for line in lines:
        match = _TOC_LINE_RE.match(line)
        if not match:
            continue
        indent = len(match.group("indent"))
        title = match.group("title").strip()
        while ancestors and ancestors[-1][0] >= indent:
            ancestors.pop()
        if selected_depth is not None and indent <= selected_depth:
            selected_depth = None
        if selected_depth is None and pattern.search(title):
            selected_depth = indent
        if selected_depth is not None:
            rel = resolve_link(base_dir, match.group("link"))
            if rel is not None and rel not in selected:
                section_titles = [t for _, t in ancestors]
                selected[rel] = (title, classify_doc_type(title, section_titles), " > ".join(section_titles))
        ancestors.append((indent, title))
    return selected


def main() -> int:
    """Emit the SPEC §3 candidate list for the SAP Help table of contents; exit 0 on success."""
    toc_path, title_match = parse_args(sys.argv)
    source = os.environ.get("PINAKES_SOURCE", "?")
    commit = os.environ.get("PINAKES_COMMIT", "?")
    print(f"sap_help_toc: resolving {source} at {commit[:12]} from {toc_path}", file=sys.stderr)

    if not os.path.isfile(toc_path):
        print(f"sap_help_toc: {toc_path} not found", file=sys.stderr)
        return 1

    pattern = re.compile(title_match)
    base_dir = os.path.dirname(toc_path)
    with open(toc_path, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    selected = select_toc_pages(lines, base_dir, pattern)
    toc_rel = os.path.normpath(toc_path)
    count_selected = 0
    count_other = 0
    for path in markdown_files(base_dir or "."):
        if path == toc_rel:
            continue
        if path in selected:
            title, doc_type, section = selected[path]
            record = {"path": path, "title": title, "doc_type": doc_type, "section": section, "selected": True}
            count_selected += 1
        else:
            record = {"path": path, "title": "", "doc_type": "", "section": "", "selected": False}
            count_other += 1
        print(json.dumps(record))

    print(f"sap_help_toc: {count_selected} selected, {count_other} other candidates", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
