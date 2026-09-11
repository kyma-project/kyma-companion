#!/usr/bin/env python3
"""Retrieval evaluation script for the Kyma doc-indexer.

Measures recall@k and MRR against a labelled query set and optionally
compares results to a baseline to catch regressions.

Usage examples
--------------
Vector mode (direct HANA similarity search):
    python evaluation/run_retrieval_eval.py \\
        --table kyma_docs --k 10 --mode vector

With baseline regression check:
    python evaluation/run_retrieval_eval.py \\
        --table kyma_docs --k 10 --mode vector \\
        --baseline evaluation/baseline.json \\
        --out evaluation/results.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Path bootstrap: when run from outside the doc_indexer package the src/
# directory must be on the path so that the indexer utils can be imported.
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_SRC_DIR = _SCRIPT_DIR.parent / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


def _load_queries(queries_file: Path) -> list[dict[str, Any]]:
    """Load and validate queries from a JSONL file."""
    queries: list[dict[str, Any]] = []
    with queries_file.open() as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {lineno}: {exc}") from exc
            for field in ("id", "kind", "query", "expected"):
                if field not in entry:
                    raise ValueError(f"Missing field '{field}' on line {lineno}")
            queries.append(entry)
    return queries


def _source_matches(chunk_source: str, expected_suffix: str) -> bool:
    """Return True if chunk_source ends with (or equals) expected_suffix.

    The chunk's ``source`` field typically looks like:
      ``<repo-name>/path/to/file.md``
    The expected suffix in queries.jsonl is written as a path suffix such as:
      ``api-gateway/docs/user/apirule-migration/01-82-migrate-allow-noop.md``
    or a directory prefix:
      ``api-gateway/docs/user``

    A match is declared when chunk_source ends with the expected_suffix *or*
    chunk_source contains the expected_suffix as a path segment boundary.
    """
    # Normalise separators
    src = chunk_source.replace("\\", "/")
    exp = expected_suffix.replace("\\", "/").rstrip("/")

    if src.endswith(exp):
        return True
    # Handle directory prefix: allow matching when the suffix appears as a
    # sub-path component (avoids partial filename matches like "user" matching
    # "super-user/...").
    return ("/" + exp + "/") in ("/" + src + "/")


def _hits_at_k(
    results: list[dict[str, Any]],
    expected: list[str],
    k: int,
) -> bool:
    """Return True if any of the top-k results matches any expected source."""
    for doc in results[:k]:
        source: str = doc.metadata.get("source", "") if hasattr(doc, "metadata") else doc.get("source", "")
        for exp in expected:
            if _source_matches(source, exp):
                return True
    return False


def _reciprocal_rank(
    results: list[dict[str, Any]],
    expected: list[str],
) -> float:
    """Return the reciprocal rank of the first relevant result (0 if none found)."""
    for rank, doc in enumerate(results, start=1):
        source: str = doc.metadata.get("source", "") if hasattr(doc, "metadata") else doc.get("source", "")
        for exp in expected:
            if _source_matches(source, exp):
                return 1.0 / rank
    return 0.0


def _run_vector_mode(
    queries: list[dict[str, Any]],
    table_name: str,
    k: int,
) -> tuple[list[dict[str, Any]], float]:
    """Run evaluation using direct HANA vector similarity search.

    Returns (per_query_results, total_elapsed_seconds).
    """
    # Import here so the script can be imported without the full indexer env.
    from langchain_community.vectorstores.hanavector import HanaDB
    from utils.hana import create_hana_connection

    from utils.models import create_embedding_factory, openai_embedding_creator
    from utils.settings import (
        DATABASE_PASSWORD,
        DATABASE_PORT,
        DATABASE_URL,
        DATABASE_USER,
        EMBEDDING_MODEL_NAME,
        get_embedding_model_config,
    )

    print(f"Connecting to HANA at {DATABASE_URL}:{DATABASE_PORT} ...")
    conn = create_hana_connection(DATABASE_URL, DATABASE_PORT, DATABASE_USER, DATABASE_PASSWORD)
    if conn is None:
        raise RuntimeError("Failed to connect to HANA database.")

    print(f"Loading embedding model '{EMBEDDING_MODEL_NAME}' ...")
    model_config = get_embedding_model_config(EMBEDDING_MODEL_NAME)
    create_embedding = create_embedding_factory(openai_embedding_creator)
    embeddings = create_embedding(model_config.name)

    db = HanaDB(connection=conn, embedding=embeddings, table_name=table_name)

    per_query: list[dict[str, Any]] = []
    t0 = time.monotonic()

    for entry in queries:
        q_start = time.monotonic()
        results = db.similarity_search(entry["query"], k=k)
        latency_ms = (time.monotonic() - q_start) * 1000

        hit5 = _hits_at_k(results, entry["expected"], k=5)
        hit10 = _hits_at_k(results, entry["expected"], k=min(k, 10))
        rr = _reciprocal_rank(results, entry["expected"])

        per_query.append(
            {
                "id": entry["id"],
                "kind": entry["kind"],
                "query": entry["query"],
                "expected": entry["expected"],
                "hit@5": hit5,
                "hit@10": hit10,
                "rr": rr,
                "latency_ms": latency_ms,
                "top_sources": [doc.metadata.get("source", "") for doc in results[:5]],
            }
        )

    total_elapsed = time.monotonic() - t0
    return per_query, total_elapsed


def _compute_metrics(per_query: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-query results into overall + per-kind metrics."""

    def _agg(rows: list[dict[str, Any]]) -> dict[str, float]:
        n = len(rows)
        if n == 0:
            return {"recall@5": 0.0, "recall@10": 0.0, "mrr": 0.0, "mean_latency_ms": 0.0, "n": 0}
        return {
            "recall@5": sum(r["hit@5"] for r in rows) / n,
            "recall@10": sum(r["hit@10"] for r in rows) / n,
            "mrr": sum(r["rr"] for r in rows) / n,
            "mean_latency_ms": sum(r["latency_ms"] for r in rows) / n,
            "n": n,
        }

    by_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in per_query:
        by_kind[r["kind"]].append(r)

    return {
        "overall": _agg(per_query),
        "by_kind": {kind: _agg(rows) for kind, rows in sorted(by_kind.items())},
    }


def _render_markdown_table(metrics: dict[str, Any]) -> str:
    """Render a Markdown summary table."""
    header = "| Slice | n | recall@5 | recall@10 | MRR | mean latency ms |"
    sep = "|---|---|---|---|---|---|"
    rows = [header, sep]

    def _row(label: str, m: dict[str, Any]) -> str:
        return (
            f"| {label} | {m['n']} "
            f"| {m['recall@5']:.3f} "
            f"| {m['recall@10']:.3f} "
            f"| {m['mrr']:.3f} "
            f"| {m['mean_latency_ms']:.1f} |"
        )

    rows.append(_row("**overall**", metrics["overall"]))
    for kind, m in metrics["by_kind"].items():
        rows.append(_row(kind, m))

    return "\n".join(rows)


def _check_regression(
    metrics: dict[str, Any],
    baseline_path: Path,
    threshold: float = 0.05,
) -> bool:
    """Return True (pass) if recall@5 does not drop more than threshold vs baseline."""
    with baseline_path.open() as f:
        baseline = json.load(f)

    if not baseline:
        print("Baseline is empty -- skipping regression check.")
        return True

    baseline_r5 = baseline.get("overall", {}).get("recall@5")
    if baseline_r5 is None:
        print("Baseline has no overall.recall@5 -- skipping regression check.")
        return True

    current_r5 = metrics["overall"]["recall@5"]
    drop = baseline_r5 - current_r5
    print(f"recall@5: baseline={baseline_r5:.3f}  current={current_r5:.3f}  drop={drop:.3f}")
    if drop > threshold:
        print(
            f"REGRESSION: recall@5 dropped by {drop:.3f} which exceeds threshold {threshold:.3f}",
            file=sys.stderr,
        )
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Run retrieval evaluation against the Kyma doc index.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--table", default="kyma_docs", help="HANA table name to query against")
    parser.add_argument("--k", type=int, default=10, help="Number of results to retrieve per query")
    parser.add_argument(
        "--mode",
        choices=["vector", "app"],
        default="vector",
        help="'vector' = direct HANA similarity_search; 'app' = reserved for future HTTP-based mode",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="Path to baseline.json; exits 1 if recall@5 drops by more than 0.05",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Write full results JSON to this path",
    )
    parser.add_argument(
        "--queries",
        type=Path,
        default=_SCRIPT_DIR / "queries.jsonl",
        help="Path to the JSONL query set",
    )
    args = parser.parse_args(argv)

    queries = _load_queries(args.queries)
    print(f"Loaded {len(queries)} queries from {args.queries}")

    if args.mode == "vector":
        per_query, elapsed = _run_vector_mode(queries, args.table, args.k)
    else:
        raise NotImplementedError("'app' mode is not yet implemented")

    metrics = _compute_metrics(per_query)
    table_md = _render_markdown_table(metrics)

    print("\n" + table_md + "\n")
    print(f"Total elapsed: {elapsed:.1f}s")

    # Write to GitHub step summary when running in CI.
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with open(step_summary, "a") as f:
            f.write("## Retrieval Evaluation Results\n\n")
            f.write(table_md + "\n")

    results_payload: dict[str, Any] = {
        "metrics": metrics,
        "per_query": per_query,
    }

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w") as f:
            json.dump(results_payload, f, indent=2)
        print(f"Results written to {args.out}")

    passed = True
    if args.baseline:
        passed = _check_regression(metrics, args.baseline)

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
