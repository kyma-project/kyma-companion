"""Unit tests for scripts/diff_metrics.py (stdlib-only baseline delta table)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# diff_metrics.py lives under tests/blackbox/scripts/, which is not on sys.path, so load it
# directly from its file path.
_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "diff_metrics.py"
_spec = importlib.util.spec_from_file_location("diff_metrics", _SCRIPT_PATH)
assert _spec and _spec.loader
diff_metrics = importlib.util.module_from_spec(_spec)
sys.modules["diff_metrics"] = diff_metrics
_spec.loader.exec_module(diff_metrics)


def test_format_number_variants() -> None:
    assert diff_metrics.format_number(5) == "5"
    assert diff_metrics.format_number(9.8188) == "9.8188"
    assert diff_metrics.format_number(9.0) == "9"
    assert diff_metrics.format_number(None) == "—"
    # trailing zeros trimmed
    assert diff_metrics.format_number(94.160) == "94.16"


def test_format_delta_signs_and_missing() -> None:
    assert diff_metrics.format_delta(10, 12) == "+2"
    assert diff_metrics.format_delta(12, 10) == "-2"
    assert diff_metrics.format_delta(5, 5) == "0"
    assert diff_metrics.format_delta(94.16, 95.0) == "+0.84"
    # non-numeric / missing side -> em dash
    assert diff_metrics.format_delta(None, 5) == "—"
    assert diff_metrics.format_delta(5, None) == "—"
    # bools are not treated as numbers
    assert diff_metrics.format_delta(True, 1) == "—"


def test_build_table_known_delta() -> None:
    baseline = {"summary": {"overall_success_rate": 94.16, "total_tokens": 362164}}
    new = {"summary": {"overall_success_rate": 96.0, "total_tokens": 360000}}
    table = diff_metrics.build_table(baseline, new)

    assert "| Metric | Baseline | New | Δ |" in table
    assert "| overall_success_rate | 94.16 | 96 | +1.84 |" in table
    assert "| total_tokens | 362164 | 360000 | -2164 |" in table


def test_build_table_new_metric_shows_dash_baseline() -> None:
    baseline = {"summary": {"total_tokens": 100}}
    new = {"summary": {"total_tokens": 100, "new_metric": 42}}
    table = diff_metrics.build_table(baseline, new)
    # new_metric absent from baseline -> baseline column is em dash, delta em dash
    assert "| new_metric | — | 42 | — |" in table


def test_build_table_skips_dict_fields() -> None:
    baseline = {"summary": {"total_tokens": 10, "tool_call_counts": {"a": 1}}}
    new = {"summary": {"total_tokens": 20, "tool_call_counts": {"a": 2}}}
    table = diff_metrics.build_table(baseline, new)
    assert "tool_call_counts" not in table
    assert "| total_tokens | 10 | 20 | +10 |" in table


def test_build_table_empty_summary() -> None:
    table = diff_metrics.build_table({}, {})
    assert "no comparable summary metrics found" in table


def test_self_diff_is_all_zero() -> None:
    summary = {"summary": {"overall_success_rate": 94.16, "total_tokens": 362164, "num_queries": 25}}
    table = diff_metrics.build_table(summary, summary)
    data_rows = [
        line for line in table.splitlines() if line.startswith("| ") and "Metric" not in line and "---" not in line
    ]
    assert data_rows
    for row in data_rows:
        assert row.rstrip().endswith("| 0 |"), row
