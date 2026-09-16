import json
import os

from langchain_core.documents import Document

from utils.logging import get_logger

logger = get_logger(__name__)

MANIFEST_FILENAME = "manifest.json"
DECISIONS_FILENAME = "decisions.jsonl"
SOURCE_META_FILENAME = "meta.json"


def has_manifest(docs_path: str) -> bool:
    """Return True if docs_path is a pinakes-materialised artifact directory.

    An empty docs_path is never treated as a manifest directory, even if a manifest.json
    happens to exist in the current working directory (e.g. doc_indexer/manifest.json,
    committed for `pinakes resolve --from-manifest`) -- os.path.join("", "manifest.json")
    would otherwise resolve to a relative, cwd-dependent path.

    Args:
        docs_path: Directory to check for a manifest.json.
    """
    if not docs_path:
        return False
    return os.path.isfile(os.path.join(docs_path, MANIFEST_FILENAME))


def _load_json(path: str) -> dict:
    """Load and parse a JSON file."""
    with open(path, encoding="utf-8") as f:
        data: dict = json.load(f)
    return data


def _load_latest_decisions(docs_path: str) -> dict[str, dict[str, str]]:
    """Read decisions.jsonl, keeping only the most recent decision per page id.

    decisions.jsonl (SPEC 2.5) is append-only; later lines override earlier ones for the
    same id. Returns an empty mapping when no decisions.jsonl is present next to the
    manifest -- honouring decisions is best-effort, not required.

    Args:
        docs_path: Directory containing manifest.json (and optionally decisions.jsonl).
    """
    path = os.path.join(docs_path, DECISIONS_FILENAME)
    decisions: dict[str, dict[str, str]] = {}
    if not os.path.isfile(path):
        return decisions

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            decisions[entry["id"]] = entry

    return decisions


def _is_excluded(page_id: str, sha256: str, decisions: dict[str, dict[str, str]]) -> bool:
    """Return True if the page has a still-valid 'exclude' decision.

    A decision only applies while its recorded sha256 still matches the page's current
    sha256 in the manifest (SPEC 2.5); a stale decision (content changed since) is
    ignored, so the page stays in the corpus until it is re-decided.
    """
    decision = decisions.get(page_id)
    if not decision:
        return False
    return decision.get("decision") == "exclude" and decision.get("sha256") == sha256


def load_manifest_documents(docs_path: str) -> list[Document]:
    """Load documents from a pinakes-materialised artifact directory.

    Reads manifest.json for the pages selected per source, joins each page with its
    source's meta.json (repo, base_url, commit) and its manifest entry (title, doc_type,
    section, sha256), and returns one Document per page carrying that metadata. Pages not
    listed in the manifest (e.g. anything under `_residue/`) are never read. A page with a
    still-valid 'exclude' decision in decisions.jsonl is skipped too, so a curator's verdict
    takes effect immediately even before the next `pinakes resolve`.

    Args:
        docs_path: Path to the materialised artifact directory (manifest.json plus one
            subdirectory per source, each with its own meta.json).

    Returns:
        One Document per selected, non-excluded page, with metadata: source, title
        (navigation title), module (source name), repo, commit, url, doc_type, section,
        path, page_id (`<source>::<path>`) and sha256.
    """
    manifest = _load_json(os.path.join(docs_path, MANIFEST_FILENAME))
    decisions = _load_latest_decisions(docs_path)

    documents: list[Document] = []
    skipped_excluded = 0
    skipped_missing = 0

    for source_name, source_entry in manifest.get("sources", {}).items():
        meta_path = os.path.join(docs_path, source_name, SOURCE_META_FILENAME)
        try:
            source_meta = _load_json(meta_path)
        except FileNotFoundError:
            logger.warning(f"Missing {SOURCE_META_FILENAME} for source '{source_name}'; skipping source.")
            continue

        repo = source_meta.get("repo", "")
        base_url = source_meta.get("base_url", "")
        commit = source_meta.get("commit", "")

        for path, page in source_entry.get("pages", {}).items():
            page_id = f"{source_name}::{path}"
            sha256 = page.get("sha256", "")

            if _is_excluded(page_id, sha256, decisions):
                skipped_excluded += 1
                logger.info(f"Skipping '{page_id}': excluded by {DECISIONS_FILENAME}")
                continue

            file_path = os.path.join(docs_path, source_name, path)
            try:
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
            except FileNotFoundError:
                skipped_missing += 1
                logger.warning(f"Page '{page_id}' listed in manifest but missing on disk at {file_path}; skipping.")
                continue

            documents.append(
                Document(
                    page_content=content,
                    metadata={
                        "source": file_path,
                        "title": page.get("title", ""),
                        "module": source_name,
                        "repo": repo,
                        "commit": commit,
                        "url": f"{base_url}/{path}",
                        "doc_type": page.get("doc_type", ""),
                        "section": page.get("section", ""),
                        "path": path,
                        "page_id": page_id,
                        "sha256": sha256,
                    },
                )
            )

    logger.info(
        f"Loaded {len(documents)} document(s) from manifest at {docs_path} "
        f"({skipped_excluded} excluded by decisions, {skipped_missing} missing on disk)"
    )
    return documents
