#!/usr/bin/env python3
"""Render a GitHub-flavored markdown table of the ``summary`` deltas between two metrics reports.

Given a baseline metrics JSON and a new metrics JSON (both as produced by
``run_a2a_evaluation.py`` / ``write_metrics_report``), print a markdown table comparing every
scalar field in their ``summary`` objects: baseline value, new value, and the signed delta.

This is used by the ``update-eval-baseline`` workflow to build the body of the automated
baseline-refresh PR, so a reviewer can see at a glance how the numbers moved.

Nested/aggregate fields (``status_counts``, ``tool_call_counts``) are objects rather than
scalars and are skipped in the table. A field present in only one report shows ``—`` for the
missing side and an empty delta.

Only the Python standard library is used, so this runs without a Poetry environment.

Usage:
    python scripts/diff_metrics.py baseline_metrics.json metrics.json
    python scripts/diff_metrics.py OLD.json NEW.json --title "Baseline deltas"
"""

from __future__ import annotations

import argparse
import json
import sys
from numbers import Real
from pathlib import Path
from typing import TypeGuard

# Preferred display order for known summary keys. Any additional scalar keys found in the
# reports are appended afterwards in their natural (baseline-first) order, so a new metric is
# never silently dropped.
PREFERRED_ORDER = [
    "num_scenarios",
    "num_queries",
    "overall_success_rate",
    "num_scenarios_retried",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "avg_tokens_per_query",
    "total_llm_call_count",
    "total_tool_call_count",
    "total_latency_seconds",
    "avg_latency_seconds",
    "total_time_minutes",
]


def load_report(path: Path) -> dict:
    """Read and parse a metrics JSON report, exiting with a clear message on error."""
    try:
        with path.open(encoding="utf-8") as file:
            data: dict = json.load(file)
            return data
    except FileNotFoundError:
        sys.exit(f"error: input file not found: {path}")
    except json.JSONDecodeError as exc:
        sys.exit(f"error: could not parse JSON in {path}: {exc}")


def is_scalar_number(value: object) -> TypeGuard[float]:
    """Return True for real numbers we can diff (ints/floats), excluding bools."""
    return isinstance(value, Real) and not isinstance(value, bool)


def format_number(value: object) -> str:
    """Format a value for the table: ints as-is, floats trimmed to at most 4 decimals."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        # Round to 4 decimals, then strip trailing zeros / dot for a compact display.
        text = f"{value:.4f}".rstrip("0").rstrip(".")
        return text if text not in ("", "-0") else "0"
    return str(value)


def format_delta(baseline: object, new: object) -> str:
    """Return a signed delta string, or '—' when a side is missing/non-numeric."""
    if not (is_scalar_number(baseline) and is_scalar_number(new)):
        return "—"
    delta = new - baseline
    if delta == 0:
        return "0"
    sign = "+" if delta > 0 else "-"
    return f"{sign}{format_number(abs(delta))}"


def ordered_scalar_keys(baseline: dict, new: dict) -> list[str]:
    """Union of keys whose value is a scalar number in either report, in display order."""
    scalar_keys = {key for source in (baseline, new) for key, value in source.items() if is_scalar_number(value)}
    ordered = [key for key in PREFERRED_ORDER if key in scalar_keys]
    extras = sorted(scalar_keys - set(ordered))
    return ordered + extras


def build_table(baseline_report: dict, new_report: dict) -> str:
    """Build a markdown table of summary deltas between two reports."""
    baseline = baseline_report.get("summary", {}) or {}
    new = new_report.get("summary", {}) or {}

    keys = ordered_scalar_keys(baseline, new)
    lines = ["| Metric | Baseline | New | Δ |", "|---|---|---|---|"]
    if not keys:
        lines.append("| _(no comparable summary metrics found)_ | — | — | — |")
        return "\n".join(lines)

    for key in keys:
        base_val = baseline.get(key)
        new_val = new.get(key)
        lines.append(
            f"| {key} | {format_number(base_val)} | {format_number(new_val)} | {format_delta(base_val, new_val)} |"
        )
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("baseline", type=Path, help="Path to the baseline metrics JSON (old values).")
    parser.add_argument("new", type=Path, help="Path to the new metrics JSON (proposed values).")
    parser.add_argument("--title", default="", help="Optional markdown heading printed above the table.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point: load both reports and print the delta table."""
    args = parse_args(argv)
    baseline_report = load_report(args.baseline)
    new_report = load_report(args.new)
    if args.title:
        print(f"### {args.title}\n")
    print(build_table(baseline_report, new_report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
