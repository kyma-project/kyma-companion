import json
import os
from typing import Any

from utils.logging import get_logger

logger = get_logger(__name__)


def build_report(
    run: Any,
    writers: list[str],
    module_counts: dict[str, int],
    duration_seconds: float,
    previous: dict[str, Any] | None,
) -> dict[str, Any]:
    """Collect the run statistics as a JSON-serializable dict.

    `run` is a RunDescriptor; `previous` is {"run_id", "total_chunks", "modules"} of the run that was current
    before this one (pgvector only), or None when unknown.
    """
    sources = {
        module: {"repo_url": (info or {}).get("repo_url"), "commit": (info or {}).get("commit")}
        for module, info in (run.sources or {}).items()
    }
    # Modules known from the manifest but without chunks are listed with 0 so they can be flagged.
    modules = {m: 0 for m in sources} | module_counts
    return {
        "run_id": run.run_id,
        "writers": writers,
        "embedding_model": run.embedding_model,
        "indexer_version": getattr(run, "indexer_version", "unknown"),
        "dimensions": run.dimensions,
        "total_chunks": sum(module_counts.values()),
        "duration_seconds": round(duration_seconds, 1),
        "modules": dict(sorted(modules.items())),
        "sources": sources,
        "previous": previous,
    }


def _delta(now: int, before: int | None) -> str:
    if before is None:
        return "n/a"
    return f"{now - before:+d}"


def render_summary(report: dict[str, Any]) -> str:
    """Render the report as GitHub-flavoured markdown."""
    previous = report.get("previous")
    prev_modules: dict[str, int] | None = previous["modules"] if previous else None
    total = report["total_chunks"]
    total_delta = f" ({_delta(total, previous['total_chunks'])} vs `{previous['run_id']}`)" if previous else ""
    lines = [
        "## Docs index run summary",
        "",
        f"Run `{report['run_id']}` | writer: {', '.join(report['writers'])} | "
        f"indexer: `{report.get('indexer_version', 'unknown')}` | "
        f"embedding: {report['embedding_model']} ({report['dimensions']} dims) | "
        f"chunks: {total}{total_delta} | index duration: {report['duration_seconds']}s",
        "",
        "| Module | Chunks | Delta | Commit |",
        "|---|---:|---:|---|",
    ]
    warnings: list[str] = []
    all_modules = sorted(set(report["modules"]) | set(prev_modules or {}))
    for module in all_modules:
        count = report["modules"].get(module, 0)
        delta = _delta(count, prev_modules.get(module, 0) if prev_modules is not None else None)
        source = report["sources"].get(module) or {}
        sha, repo = source.get("commit"), source.get("repo_url")
        commit = "-"
        if sha:
            commit = f"[`{sha[:7]}`]({repo}/commit/{sha})" if repo else f"`{sha[:7]}`"
        name = module
        if count == 0:
            name = f"{module} :warning:"
            if module in report["modules"]:
                warnings.append(f"`{module}` has 0 chunks")
            else:
                warnings.append(f"`{module}` was in the previous run but is missing now")
        lines.append(f"| {name} | {count} | {delta} | {commit} |")
    lines.append("")
    lines.append("Warnings: " + ("; ".join(warnings) if warnings else "none"))
    return "\n".join(lines) + "\n"


def emit_summary(markdown: str, summary_path: str, github_step_summary: str | None) -> None:
    """Log the summary (one message), and write/append it to the configured files."""
    logger.info("Index run summary:\n" + markdown)
    if summary_path:
        with open(summary_path, "w", encoding="utf-8") as fh:
            fh.write(markdown)
    if github_step_summary:
        with open(github_step_summary, "a", encoding="utf-8") as fh:
            fh.write(markdown + "\n")


def report_json(report: dict[str, Any]) -> str:
    """Serialize the report for storage."""
    return json.dumps(report)


def github_step_summary_path() -> str | None:
    """Return the file GitHub Actions renders as job summary, if running there."""
    return os.environ.get("GITHUB_STEP_SUMMARY") or None
