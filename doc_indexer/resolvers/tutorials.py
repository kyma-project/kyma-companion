#!/usr/bin/env python3
"""External pinakes resolver (SPEC §3) for `sap-tutorials` repositories.

Reimplements ``resolve_tutorials`` from ``doc_indexer/src/fetcher/resolvers.py`` as a
dependency-free script pinakes can run directly against a checkout, without importing anything
from the ``doc_indexer`` package (pinakes ships this file standalone).

The tutorial repositories tag Kyma content inconsistently (three spellings of the same
``primary_tag`` exist in the wild), while the tutorial directory name is reliable, so both the
path and the frontmatter tags are checked against *match* (case-insensitive substring).

Usage: ``tutorials.py [ROOT] [MATCH]``, run with cwd = the repository checkout. Default
``ROOT`` is ``tutorials``, default ``MATCH`` is ``kyma``.
"""

from __future__ import annotations

import json
import os
import re
import sys

_H1_RE = re.compile(r"^#\s+(?P<title>.+?)\s*#*\s*$", re.MULTILINE)
_FRONTMATTER_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")


def frontmatter(text: str) -> dict[str, str]:
    """Return the top-level scalar keys of a YAML frontmatter block, or ``{}``."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    result: dict[str, str] = {}
    for line in text[3:end].splitlines():
        match = _FRONTMATTER_KEY_RE.match(line)
        if match:
            result[match.group(1)] = match.group(2).strip().strip("'\"")
    return result


def first_h1(text: str) -> str:
    """Return the first ``# Heading`` outside frontmatter, or an empty string."""
    body = text
    if body.startswith("---"):
        end = body.find("\n---", 3)
        if end != -1:
            body = body[end + 4 :]
    match = _H1_RE.search(body)
    return match.group("title").strip() if match else ""


def markdown_files(root: str) -> list[str]:
    """Return every ``.md`` path under *root*, relative to the repository root, sorted."""
    found: list[str] = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for filename in filenames:
            if filename.endswith(".md"):
                found.append(os.path.relpath(os.path.join(dirpath, filename), "."))
    return sorted(found)


_ARGV_ROOT = 1
_ARGV_MATCH = 2


def parse_args(argv: list[str]) -> tuple[str, str]:
    """Return ``(root, match)`` from CLI arguments, applying the documented defaults."""
    root = argv[_ARGV_ROOT] if len(argv) > _ARGV_ROOT else "tutorials"
    match = argv[_ARGV_MATCH] if len(argv) > _ARGV_MATCH else "kyma"
    return root, match


def main() -> int:
    """Emit the SPEC §3 candidate list for the tutorials directory; exit 0 on success."""
    root, match = parse_args(sys.argv)
    source = os.environ.get("PINAKES_SOURCE", "?")
    commit = os.environ.get("PINAKES_COMMIT", "?")
    print(f"tutorials: resolving {source} at {commit[:12]} under {root}/", file=sys.stderr)

    if not os.path.isdir(root):
        print(f"tutorials: no {root}/ directory", file=sys.stderr)
        return 0

    needle = match.lower()
    count_selected = 0
    count_other = 0
    for path in markdown_files(root):
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
        except OSError as err:
            print(f"tutorials: {path}: {err}", file=sys.stderr)
            return 1
        meta = frontmatter(text)
        tags = " ".join(v for k, v in meta.items() if k in ("tags", "primary_tag", "keywords")).lower()
        selected = needle in path.lower() or needle in tags
        if selected:
            title = meta.get("title") or first_h1(text)
            record = {"path": path, "title": title, "doc_type": "tutorial", "section": root, "selected": True}
            count_selected += 1
        else:
            record = {"path": path, "title": "", "doc_type": "", "section": "", "selected": False}
            count_other += 1
        print(json.dumps(record))

    print(f"tutorials: {count_selected} selected, {count_other} other candidates", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
