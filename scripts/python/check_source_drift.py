"""Audit existing docs_sources.json entries for doc drift in tracked repos.

For each tracked repo, checks:
  NEW_PATH — doc directories present in the repo but not covered by
             include_files
  DEAD     — include_files patterns that match no files in the repo

Usage:
    python scripts/python/check_source_drift.py
    python scripts/python/check_source_drift.py --auto-fix
    python scripts/python/check_source_drift.py --repo api-gateway
    python scripts/python/check_source_drift.py \\
        --sources doc_indexer/docs_sources.json
"""

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

SOURCES_DEFAULT = (
    Path(__file__).parent.parent.parent / "doc_indexer/docs_sources.json"
)

# Top-level doc directory roots worth scanning for drift.
DOC_ROOTS = ["docs", "tutorials"]

# Second-level subdirectory names under a doc root that are NOT user-facing.
# Files under these paths are skipped when detecting NEW_PATH drift so that
# contributor guides, release notes, and asset directories never appear as
# uncovered user-doc paths in kyma-companion's user-only scope.
_SKIP_DOC_SUBDIRS = {
    "contributor",
    "release-notes",
    "release_notes",
    "assets",
    "images",
    "img",
    "figures",
    "operator",      # platform-operator/admin guides, not end-user docs
    "agents",        # AI-agent coding guides, developer-facing
    "adr",           # Architecture Decision Records, developer-facing
    "internal",      # internal architecture/design docs
    "contributing",  # contribution process docs, developer-facing
    "governance",    # project governance, not product docs
    "guidelines",    # development guidelines, developer-facing
    "loadtest",      # load-testing tooling, developer-facing
}


def gh_json(endpoint: str) -> dict | list | None:
    result = subprocess.run(
        ["gh", "api", endpoint],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def get_repo_md_files(org: str, repo: str) -> list[str]:
    """Return all .md file paths in the repo via the git tree API."""
    data = gh_json(f"repos/{org}/{repo}/git/trees/HEAD?recursive=1")
    if not data or not isinstance(data, dict):
        return []
    return [
        item["path"]
        for item in data.get("tree", [])
        if item.get("type") == "blob"
        and item["path"].lower().endswith(".md")
    ]


def repo_name_from_url(url: str) -> tuple[str, str]:
    """Return (org, repo) from a GitHub clone URL."""
    path = urlparse(url).path.strip("/").removesuffix(".git")
    parts = path.split("/")
    return parts[-2], parts[-1]


def is_covered(file_path: str, include_files: list[str] | None) -> bool:
    if include_files is None:
        return True
    return any(fnmatch.fnmatch(file_path, p) for p in include_files)


def infer_doc_roots(include_files: list[str] | None) -> set[str]:
    """Derive top-level doc directories implied by include_files patterns."""
    if not include_files:
        return set(DOC_ROOTS)
    roots = set()
    for pattern in include_files:
        top = pattern.split("/")[0]
        if top and top not in ("README.md", "CONTRIBUTING.md"):
            roots.add(top)
    return roots or set(DOC_ROOTS)


def check_source(source: dict, all_md_files: list[str]) -> dict:
    """Return drift findings for one source entry."""
    include_files = source.get("include_files")
    doc_roots = infer_doc_roots(include_files)

    # Only look at files under relevant doc roots
    candidate_files = [
        f for f in all_md_files if f.split("/")[0] in doc_roots
    ]

    # NEW_PATH: doc files not covered by include_files
    uncovered = [
        f for f in candidate_files
        if not is_covered(f, include_files)
    ]
    # Summarise by directory (avoid listing every individual file).
    # Skip non-user subdirs (e.g. docs/contributor/, docs/release-notes/) —
    # this repo indexes user docs only.
    uncovered_dirs: set[str] = set()
    for f in uncovered:
        parts = f.split("/")
        if len(parts) >= 2 and parts[1] in _SKIP_DOC_SUBDIRS:
            continue
        # Build a directory summary: strip the filename (parts[:-1]) and
        # cap at 3 levels so deep trees are collapsed to their top subdir.
        parent = parts[:-1]
        # Skip loose files directly under the doc root (e.g. docs/README.md,
        # docs/CLAUDE.md) — these are meta/nav files, not new doc directories.
        if len(parent) <= 1:
            continue
        summary = "/".join(parent[:3])
        uncovered_dirs.add(summary + "/")

    # DEAD: patterns that match nothing
    dead_patterns = []
    if include_files:
        for pattern in include_files:
            if not any(fnmatch.fnmatch(f, pattern) for f in all_md_files):
                dead_patterns.append(pattern)

    # BROAD: include_files has docs/* but repo actually has docs/user/
    # structure — docs/* is too permissive and pulls in release-notes, etc.
    broad_patterns = []
    if include_files and any(f.startswith("docs/user/") for f in all_md_files):
        broad_patterns = [p for p in include_files if p == "docs/*"]

    return {
        "uncovered_dirs": sorted(uncovered_dirs),
        "dead_patterns": dead_patterns,
        "broad_patterns": broad_patterns,
    }


def _deduplicate_patterns(patterns: list[str]) -> list[str]:
    """Remove patterns already covered by a broader sibling in the same list.

    e.g. if docs/user/* and docs/user/architecture/* both exist,
    docs/user/architecture/* is redundant and gets removed.
    """
    result = []
    for p in patterns:
        representative = (p[:-1] + "x.md") if p.endswith("/*") else p
        covered = any(
            other != p and fnmatch.fnmatch(representative, other)
            for other in patterns
        )
        if not covered:
            result.append(p)
    return result


def apply_fixes(source: dict, findings: dict) -> dict:
    """Return updated source entry with drift fixes applied."""
    updated = dict(source)
    include_files = list(source.get("include_files") or [])

    # Fix BROAD: replace docs/* with docs/user/* when docs/user/ exists
    for p in findings.get("broad_patterns", []):
        if p in include_files:
            include_files.remove(p)
            if "docs/user/*" not in include_files:
                include_files.append("docs/user/*")

    # Add conservative glob patterns for uncovered directories.
    # Skip if the directory is already covered by a broader existing pattern
    # (e.g. docs/user/* already covers docs/user/architecture/).
    for d in findings["uncovered_dirs"]:
        pattern = d.rstrip("/") + "/*"
        if pattern in include_files:
            continue
        representative = d.rstrip("/") + "/x.md"
        if any(fnmatch.fnmatch(representative, p) for p in include_files):
            continue
        include_files.append(pattern)

    # Remove dead patterns
    for p in findings["dead_patterns"]:
        if p in include_files:
            include_files.remove(p)

    # Remove any patterns now made redundant by a broader sibling
    include_files = _deduplicate_patterns(include_files)

    if include_files != list(source.get("include_files") or []):
        updated["include_files"] = include_files

    return updated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default=str(SOURCES_DEFAULT))
    parser.add_argument("--repo", help="Audit a single repo by name")
    parser.add_argument(
        "--auto-fix",
        action="store_true",
        help="Automatically apply fixes to docs_sources.json",
    )
    args = parser.parse_args()

    sources_path = Path(args.sources)
    if not sources_path.exists():
        print(f"ERROR: {sources_path} not found")
        sys.exit(1)

    with open(sources_path, encoding="utf-8") as f:
        sources = json.load(f)

    if args.repo:
        sources = [s for s in sources if s["name"] == args.repo]
        if not sources:
            print(f"ERROR: repo '{args.repo}' not found in sources")
            sys.exit(1)

    found_any = False
    updated_sources = []

    for source in sources:
        name = source["name"]
        url = source.get("url", "")
        try:
            org, repo = repo_name_from_url(url)
        except (IndexError, ValueError):
            updated_sources.append(source)
            continue

        all_md = get_repo_md_files(org, repo)
        if not all_md:
            print(f"  SKIP  {name}  (no files returned or repo inaccessible)")
            updated_sources.append(source)
            continue

        findings = check_source(source, all_md)

        lines = []
        for d in findings["uncovered_dirs"]:
            lines.append(f"    NEW_PATH  {d}")
        for p in findings["dead_patterns"]:
            lines.append(f"    DEAD      {p}")
        for p in findings["broad_patterns"]:
            lines.append(
                f"    BROAD     {p}"
                "  (docs/user/ exists — narrowed to docs/user/*)"
            )

        if lines:
            found_any = True
            print(f"\n{name}")
            for line in lines:
                print(line)

        if args.auto_fix and lines:
            updated_sources.append(apply_fixes(source, findings))
        else:
            updated_sources.append(source)

    if not found_any:
        print("\nNo drift found in any tracked source.")
    else:
        if args.auto_fix:
            sources_path.write_text(
                json.dumps(updated_sources, indent=2) + "\n",
                encoding="utf-8",
            )
            print(
                "\nAuto-fixed. Review changes with"
                " /triage-companion-doc-sources before merging."
            )
        else:
            print(
                "\nRe-run with --auto-fix to apply these fixes"
                " to docs_sources.json."
            )


if __name__ == "__main__":
    main()
