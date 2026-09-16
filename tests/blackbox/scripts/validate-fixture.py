#!/usr/bin/env python3
"""Validate that a KWOK fixture produces the same companion answers as a real cluster.

Usage:
    cd tests/blackbox
    python scripts/validate-fixture.py \\
        --scenario data/test-cases/01_bitnami_role_missing \\
        --config /tmp/kwok-eval-config.json

The script sends each query from scenario.yml to the companion using the
cluster credentials in --config, then scores each expectation with deepeval
(the same GEval scorer the main eval uses).

Exit codes:
    0  all required expectations passed
    1  one or more required expectations failed
    2  usage / configuration error
"""

import argparse
import sys
import textwrap
from pathlib import Path
from typing import Any

import yaml


def _load_scenario(scenario_dir: Path) -> dict[str, Any]:
    path = scenario_dir / "scenario.yml"
    if not path.exists():
        print(f"ERROR: {path} not found", file=sys.stderr)
        sys.exit(2)
    with path.open() as f:
        result: dict[str, Any] = yaml.safe_load(f) or {}
        return result


def _setup_sys_path(script_dir: Path) -> None:
    src = script_dir.parent / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))


def _build_config(config_path: Path) -> Any:
    """Instantiate Config, overriding CONFIG_PATH to point at the KWOK config.json."""
    import os

    os.environ["CONFIG_PATH"] = str(config_path)
    from common.config import Config  # noqa: PLC0415

    return Config()


def _build_validator(config: Any) -> Any:
    from evaluation.validator.utils import create_validator  # noqa: PLC0415

    return create_validator(config)


def _send_query(
    a2a_client: Any,
    query: dict[str, Any],
    context_id: str | None,
) -> tuple[str, str]:
    """Send one query; return (answer, new_context_id)."""
    resource = query.get("resource", {})
    result = a2a_client.send_message(
        query=query["user_query"],
        resource_kind=resource.get("kind", ""),
        resource_name=resource.get("name", ""),
        resource_api_version=resource.get("api_version", ""),
        namespace=resource.get("namespace", ""),
        context_id=context_id,
    )
    return result.answer, result.context_id


def _score_query(validator: Any, user_query: str, actual_response: str, expectations: list[dict]) -> list[dict]:
    """Run deepeval GEval on one query; return per-expectation results."""
    from evaluation.scenario.scenario import Expectation, Query, Resource  # noqa: PLC0415

    query_obj = Query(
        user_query=user_query,
        resource=Resource(kind="", api_version="", name="", namespace=""),
        expectations=[Expectation(**e) for e in expectations],
    )
    query_obj.actual_response = actual_response

    result = validator.get_deepeval_evaluate(query_obj)
    test_result = result.test_results[0]

    out = []
    for metric in test_result.metrics_data:
        out.append(
            {
                "name": metric.name,
                "score": metric.score,
                "passed": metric.success,
                "reason": metric.reason or "",
            }
        )
    return out


def _print_result(query_text: str, answer: str, scored: list[dict]) -> bool:
    """Print per-expectation results; return True if all required ones passed."""
    all_required_passed = True
    print(f"\n  Query: {query_text!r}")
    wrapped = textwrap.fill(answer, width=90, initial_indent="  Answer: ", subsequent_indent="           ")
    print(wrapped)
    print()
    for item in scored:
        is_required = item["name"].startswith("required_")
        label = "REQUIRED" if is_required else "optional"
        icon = "PASS" if item["passed"] else "FAIL"
        score_str = f"{item['score']:.2f}" if item["score"] is not None else "n/a"
        print(f"    [{icon}] [{label}] {item['name']}  score={score_str}")
        if not item["passed"] and item["reason"]:
            reason_wrapped = textwrap.fill(
                item["reason"], width=86, initial_indent="           reason: ", subsequent_indent="                   "
            )
            print(reason_wrapped)
        if is_required and not item["passed"]:
            all_required_passed = False
    return all_required_passed


def _run_queries(a2a_client: Any, validator: Any, queries: list[dict]) -> bool:
    """Send all queries and score them; return True when all required expectations pass."""
    context_id: str | None = None
    all_passed = True

    for i, query in enumerate(queries, start=1):
        print(f"\n--- Query {i}/{len(queries)} ---")
        try:
            answer, context_id = _send_query(a2a_client, query, context_id)
        except Exception as exc:
            print(f"  ERROR sending query: {exc}", file=sys.stderr)
            all_passed = False
            continue

        try:
            scored = _score_query(validator, query["user_query"], answer, query.get("expectations", []))
        except Exception as exc:
            print(f"  ERROR scoring query: {exc}", file=sys.stderr)
            all_passed = False
            continue

        if not _print_result(query["user_query"], answer, scored):
            all_passed = False

    return all_passed


def main() -> None:
    """Entry point: validate a KWOK fixture against scenario expectations."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenario", required=True, help="Path to the scenario directory")
    parser.add_argument("--config", required=True, help="Path to config.json (e.g. from replay-fixture.sh)")
    args = parser.parse_args()

    scenario_dir = Path(args.scenario).resolve()
    config_path = Path(args.config).resolve()

    if not config_path.exists():
        print(f"ERROR: config not found: {config_path}", file=sys.stderr)
        sys.exit(2)

    script_dir = Path(__file__).parent
    _setup_sys_path(script_dir)

    scenario = _load_scenario(scenario_dir)
    scenario_id = scenario.get("id", scenario_dir.name)
    queries = scenario.get("queries", [])

    if not queries:
        print(f"Scenario {scenario_id} has no queries — nothing to validate.")
        sys.exit(0)

    fixture_ns = scenario.get("fixture", {}).get("namespace", "")
    print(f"\nValidating scenario: {scenario_id}")
    if fixture_ns:
        print(f"Namespace:           {fixture_ns}")
    print(f"Config:              {config_path}")
    print(f"Queries:             {len(queries)}")

    config = _build_config(config_path)
    validator = _build_validator(config)

    from evaluation.companion.a2a_client import A2AClient, A2AEncryptionSession  # noqa: PLC0415

    try:
        enc_session = A2AEncryptionSession.create(config)
    except Exception as exc:
        print(f"ERROR: failed to create A2A encryption session: {exc}", file=sys.stderr)
        sys.exit(2)

    a2a_client = A2AClient(config, enc_session)
    all_passed = _run_queries(a2a_client, validator, queries)

    print()
    if all_passed:
        print(f"RESULT: PASS — all required expectations satisfied for {scenario_id}")
        sys.exit(0)
    else:
        print(f"RESULT: FAIL — one or more required expectations failed for {scenario_id}")
        sys.exit(1)


if __name__ == "__main__":
    main()
