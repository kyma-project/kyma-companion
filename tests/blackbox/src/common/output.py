import json
import os
from typing import Any, Literal

import github_action_utils as gha_utils
from deepeval.evaluate.utils import print_test_result
from deepeval.test_run.test_run import TestRunResultDisplay
from evaluation.companion.response_models import ConversationResponseChunk
from evaluation.scenario.enums import TestStatus
from evaluation.scenario.scenario import Expectation, Query, Scenario, ScenarioList
from prettytable import PrettyTable
from termcolor import colored

from common.metrics import Metrics

# Constants
REASON_PREVIEW_MAX_LENGTH = 200


def print_header(name: str) -> None:
    """Prints a header with a name."""
    print("\n************************************************************************")
    print(f"*** {name}")
    print("************************************************************************\n")


def print_separator(char: str = "-", length: int = 80) -> None:
    """Prints a separator line."""
    print(char * length)


def _print_query_header(scenario: Scenario, query: Query) -> None:
    """Prints the header section with scenario description and query details."""
    print_separator("=")
    print(colored(f"Description: {scenario.description}", "cyan"))
    print_separator("=")
    print()

    print(colored("Query:", "yellow"), f'"{query.user_query}"')
    print(colored("Resource Context:", "yellow"))
    print(f"  - Kind: {query.resource.kind}")
    print(f"  - Name: {query.resource.name}")
    print(f"  - Namespace: {query.resource.namespace}")
    print()


def _print_agent_response(query: Query) -> None:
    """Prints the agent response section."""
    print_separator()
    print(colored("Agent Response:", "yellow"))
    print_separator()
    if query.actual_response:
        response_lines = query.actual_response.split("\n")
        for line in response_lines:
            print(line)
    else:
        print(colored("(No response received)", "red"))
    print()


def _print_query_metrics(query: Query) -> None:
    """Prints the per-query performance metrics (latency, tokens, tool calls)."""
    m = query.metrics
    print_separator()
    print(colored("Query Metrics:", "yellow"))
    print_separator()
    print(f"  - Latency: {m.latency_seconds}s (eval: {m.evaluation_latency_seconds}s)")
    print(f"  - Tokens: {m.total_tokens} (input: {m.input_tokens}, output: {m.output_tokens})")
    print(f"  - LLM calls: {m.llm_call_count} | Tool calls: {m.tool_call_count}")
    if m.tool_call_counts:
        tools = ", ".join(f"{name}×{count}" for name, count in m.tool_call_counts.items())
        print(f"  - Tools used: {tools}")
    print(f"  - Response size: {m.response_char_count} chars, {m.response_word_count} words")
    print()


def _print_expectation_statement(expectation: Expectation) -> None:
    """Prints the expectation statement with proper wrapping."""
    statement_lines = expectation.statement.split("\n")
    for i, line in enumerate(statement_lines):
        if i == 0:
            print(f'   Statement: "{line}"')
        else:
            print(f"              {line}")


def _print_expectation_result_status(score: float, threshold: float, passed: bool) -> None:
    """Prints the result status with appropriate coloring for borderline cases."""
    if passed:
        if score < threshold + 0.1 and score > threshold:
            print(
                colored(
                    f"   Result: PASS (borderline!) - Score {score:.2f} just above threshold {threshold}",
                    "yellow",
                )
            )
        else:
            print(colored("   Result: PASS", "green"))
    else:
        if score >= threshold - 0.1:
            print(colored(f"   Result: FAIL (close) - Score {score:.2f} just below threshold {threshold}", "yellow"))
        else:
            print(colored("   Result: FAIL", "red"))


def _print_metric_reason(metric_data: Any) -> None:
    """Prints the metric reason if available, with truncation for long reasons."""
    if hasattr(metric_data, "reason") and metric_data.reason:
        reason_preview = metric_data.reason[:REASON_PREVIEW_MAX_LENGTH]
        if len(metric_data.reason) > REASON_PREVIEW_MAX_LENGTH:
            reason_preview += "..."
        print(f"   Reason: {reason_preview}")


def _check_borderline_expectations(query: Query, test_result: Any) -> bool:
    """Checks if any required expectations have borderline passing scores."""
    if not test_result.metrics_data:
        return False

    for expectation, metric_data in zip(query.expectations, test_result.metrics_data, strict=False):
        if (
            expectation.required
            and metric_data.score is not None
            and metric_data.score < expectation.threshold + 0.1
            and metric_data.score >= expectation.threshold
        ):
            return True
    return False


def _print_expectations_summary(
    required_passed: int,
    required_total: int,
    optional_passed: int,
    optional_total: int,
    has_borderline: bool,
) -> None:
    """Prints the final summary of expectation results."""
    print_separator()
    overall_passed = required_passed == required_total

    summary_color: Literal["green", "red"]
    if overall_passed:
        summary_color = "green"
        status_icon = "✅"
        status_text = "TEST PASSED"
    else:
        summary_color = "red"
        status_icon = "❌"
        status_text = "TEST FAILED"

    borderline_note = ""
    if has_borderline and overall_passed:
        borderline_note = colored(
            "\n   ⚠️  Note: One or more required expectations passed with scores close to threshold",
            "yellow",
        )

    summary_msg = (
        f"{status_icon} {status_text} (Required: {required_passed}/{required_total} | "
        f"Optional: {optional_passed}/{optional_total}){borderline_note}"
    )
    print(colored(summary_msg, summary_color, attrs=["bold"]))
    print_separator()
    print()


def print_detailed_query_results(scenario: Scenario, query: Query) -> None:
    """Prints detailed results for a query including response and expectation breakdown."""
    _print_query_header(scenario, query)
    _print_agent_response(query)
    _print_query_metrics(query)

    # Print expectation results
    if not (query.evaluation_result and query.evaluation_result.test_results):
        return

    test_result = query.evaluation_result.test_results[0]

    # Check if metrics_data is available
    if not test_result.metrics_data:
        return

    # Count required vs optional expectations
    required_count = sum(1 for exp in query.expectations if exp.required)
    optional_count = len(query.expectations) - required_count

    print_separator()
    expectation_header = (
        f"Expectation Results ({len(query.expectations)} total, {required_count} required, {optional_count} optional):"
    )
    print(colored(expectation_header, "yellow"))
    print_separator()
    print()

    # Track pass/fail counts
    required_passed = 0
    required_total = 0
    optional_passed = 0
    optional_total = 0

    # Print each expectation with its result
    for expectation, metric_data in zip(query.expectations, test_result.metrics_data, strict=False):
        # Determine if required or optional
        req_type = (
            colored("[REQUIRED]", "red", attrs=["bold"]) if expectation.required else colored("[OPTIONAL]", "blue")
        )

        # Get score and threshold
        score = metric_data.score
        threshold = expectation.threshold

        # Skip if score is None
        if score is None:
            continue

        # Determine pass/fail
        passed = score >= threshold
        status_icon = "✅" if passed else "❌"

        # Track counts
        if expectation.required:
            required_total += 1
            if passed:
                required_passed += 1
        else:
            optional_total += 1
            if passed:
                optional_passed += 1

        # Print expectation result
        print(f"{status_icon} {req_type} {expectation.name} (score: {score:.2f}, threshold: {threshold})")

        _print_expectation_statement(expectation)
        _print_expectation_result_status(score, threshold, passed)
        _print_metric_reason(metric_data)

        print()

    # Print summary
    has_borderline = _check_borderline_expectations(query, test_result)
    _print_expectations_summary(required_passed, required_total, optional_passed, optional_total, has_borderline)


def colored_status(status: TestStatus) -> str:
    """Returns the colored status of the test."""
    if status == TestStatus.PASSED:
        return colored(status.upper(), "green")
    elif status == TestStatus.FAILED:
        return colored(status.upper(), "red")
    elif status == TestStatus.COMPLETED:
        return colored(status.upper(), "blue")
    elif status == TestStatus.PENDING:
        return colored(status.upper(), "yellow")
    return colored(status.upper(), "red")


def print_test_results(scenario_list: ScenarioList, total_usage: dict[str, int], time_taken: float) -> None:
    """Prints the test results."""
    print_header("Test Results:")
    print_results_per_scenario(scenario_list)
    print_retry_summary(scenario_list)
    print_response_times_summary()
    print_scenario_metrics(scenario_list)
    print_token_usage(total_usage)
    print_header(f"Total time taken by evaluation tests: {time_taken} minutes.")
    print_overall_results(scenario_list)
    print_failed_queries(scenario_list)


def print_initial_questions(questions: list[str]) -> None:
    """Prints the initial questions."""
    for i, q in enumerate(questions):
        print(f"\t{i + 1}: {q}")


def print_response_chunks(chunks: list[ConversationResponseChunk]) -> None:
    """Prints the response chunks."""
    print(colored("==> Response chunks:", "yellow"))
    if len(chunks) == 0:
        return None
    print(json.dumps([chunk.model_dump() for chunk in chunks], indent=4))
    return None


def print_results_per_scenario(scenario_list: ScenarioList) -> None:
    """Prints the results per scenario."""
    for scenario in scenario_list.items:
        # Add attempt information if retry was used
        attempt_info = ""
        if scenario.attempt_number > 1:
            attempt_info = f" (Attempt {scenario.attempt_number})"

        with gha_utils.group(
            f"Scenario ID: {scenario.id} (Test Status: {colored_status(scenario.test_status)}){attempt_info}"
        ):
            print(colored(f"Description: {scenario.description}", "green"))

            # print initial questions.
            print_header(f"* Scenario ID: {scenario.id}, Initial Questions:")
            print_initial_questions(scenario.initial_questions)

            # for each query print the evaluation results.
            for query in scenario.queries:
                print_header(f"** Scenario ID: {scenario.id}, Query: {query.user_query}")

                # print the response chunks.
                print_response_chunks(query.response_chunks)

                # print the evaluation results.
                if query.evaluation_result is not None:
                    for test_result in query.evaluation_result.test_results:
                        print_test_result(test_result, TestRunResultDisplay.ALL)

                # print the failure reason for the query.
                if query.test_status_reason != "":
                    print(f"*** Query Status Reason: {colored(query.test_status_reason, 'red')}")

            # print failure reason for the scenario.
            if scenario.test_status_reason != "":
                print(f"*** Scenario Status Reason: {colored(scenario.test_status_reason, 'red')}")


def print_retry_summary(scenario_list: ScenarioList) -> None:
    """Prints summary of scenarios that required retries."""
    retried_scenarios = [s for s in scenario_list.items if s.attempt_number > 1]

    if not retried_scenarios:
        return

    print_header("Retry Summary:")
    print(
        colored(
            f"Total scenarios that required retries: {len(retried_scenarios)}",
            "yellow",
        )
    )

    for scenario in retried_scenarios:
        if scenario.test_status != TestStatus.FAILED:
            status_text = colored(scenario.test_status.upper(), "green")
        else:
            status_text = colored(scenario.test_status.upper(), "red")
        print(f"  - Scenario ID: {scenario.id} | Attempts: {scenario.attempt_number} | Final Status: {status_text}")
        print()


def print_failed_queries(scenario_list: ScenarioList) -> None:
    """Prints the failed queries."""
    failed_queries = []
    for scenario in scenario_list.items:
        for query in scenario.queries:
            if query.test_status == TestStatus.FAILED:
                failed_queries.append(f"Scenario ID: {scenario.id}, Query: {query.user_query}")

    if len(failed_queries) == 0:
        return None

    print_header("List of failed test case:")
    for failed_query in failed_queries:
        print(colored(f"- {failed_query}", "red"))
    return None


def print_overall_results(scenario_list: ScenarioList) -> None:
    """Prints the overall results."""
    print_header(f"Overall success score across all expectations: {scenario_list.get_overall_success_rate()}%")


def print_response_times_summary() -> None:
    """Prints the response times summary."""
    table = PrettyTable()
    table.field_names = [
        "API Endpoint",
        "Response Time (seconds)",
    ]

    print_header("Response time per API Endpoint:")
    metrics = Metrics.get_instance()
    if metrics.conversation_response_times_sec:
        table.add_row(
            [
                "POST /api/agent/kyma/chat",
                metrics.get_conversation_response_summary(),
            ]
        )
    print(table)


def print_token_usage(token_used: dict[str, int]) -> None:
    """Prints the token usage summary, separated into input and output tokens."""
    print_header("Token usage by evaluation tests:")
    table = PrettyTable()
    table.field_names = ["Token Type", "Count"]
    table.add_row(["Input tokens", token_used.get("input", 0)])
    table.add_row(["Output tokens", token_used.get("output", 0)])
    table.add_row(["Total tokens", token_used.get("total", 0)])
    print(table)


def print_scenario_metrics(scenario_list: ScenarioList) -> None:
    """Prints a per-scenario metrics table and a run-level metrics summary."""
    report = scenario_list.build_metrics_report()

    print_header("Per-scenario metrics:")
    table = PrettyTable()
    table.field_names = [
        "Scenario ID",
        "Queries",
        "Total Tokens",
        "Avg Tokens/Query",
        "LLM Calls",
        "Tool Calls",
        "Total Latency (s)",
        "Avg Latency (s)",
    ]
    for scenario in report["scenarios"]:
        table.add_row(
            [
                scenario["scenario_id"],
                scenario["num_queries"],
                scenario["total_tokens"],
                scenario["avg_tokens_per_query"],
                scenario["llm_call_count"],
                scenario["tool_call_count"],
                scenario["total_latency_seconds"],
                scenario["avg_latency_seconds"],
            ]
        )
    print(table)

    summary = report["summary"]
    print_header("Run-level metrics summary:")
    summary_table = PrettyTable()
    summary_table.field_names = ["Metric", "Value"]
    summary_table.add_row(["Scenarios", summary["num_scenarios"]])
    summary_table.add_row(["Queries", summary["num_queries"]])
    summary_table.add_row(["Total tokens", summary["total_tokens"]])
    summary_table.add_row(["Avg tokens/query", summary["avg_tokens_per_query"]])
    summary_table.add_row(["Total LLM calls", summary["total_llm_call_count"]])
    summary_table.add_row(["Total tool calls", summary["total_tool_call_count"]])
    summary_table.add_row(["Total latency (s)", summary["total_latency_seconds"]])
    summary_table.add_row(["Avg latency/query (s)", summary["avg_latency_seconds"]])
    print(summary_table)

    if summary["tool_call_counts"]:
        print_header("Tool usage across all scenarios:")
        tool_table = PrettyTable()
        tool_table.field_names = ["Tool", "Call Count"]
        for name, count in sorted(summary["tool_call_counts"].items(), key=lambda kv: kv[1], reverse=True):
            tool_table.add_row([name, count])
        print(tool_table)


def write_metrics_report(scenario_list: ScenarioList, time_taken_minutes: float, path: str | None = None) -> str:
    """Write the machine-readable metrics report to a JSON file and return its path.

    The output path can be overridden via the ``METRICS_REPORT_PATH`` env var.
    """
    output_path: str = path or os.getenv("METRICS_REPORT_PATH") or "metrics.json"
    report = scenario_list.build_metrics_report()
    report["summary"]["total_time_minutes"] = time_taken_minutes
    with open(output_path, "w") as file:
        json.dump(report, file, indent=2)
    print_header(f"Metrics report written to: {output_path}")
    return output_path
