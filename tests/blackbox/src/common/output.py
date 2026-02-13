import json

import github_action_utils as gha_utils
from deepeval.evaluate.utils import print_test_result
from deepeval.test_run.test_run import TestRunResultDisplay
from evaluation.companion.response_models import ConversationResponseChunk
from evaluation.scenario.enums import TestStatus
from evaluation.scenario.scenario import ScenarioList
from prettytable import PrettyTable
from termcolor import colored

from common.metrics import Metrics


def print_header(name: str) -> None:
    """Prints a header with a name."""
    print("\n************************************************************************")
    print(f"*** {name}")
    print("************************************************************************\n")


def print_separator(char: str = "-", length: int = 80) -> None:
    """Prints a separator line."""
    print(char * length)


def print_detailed_query_results(scenario, query) -> None:
    """Prints detailed results for a query including response and expectation breakdown."""
    from evaluation.scenario.scenario import Query, Scenario

    print_separator("=")
    print(colored(f"Description: {scenario.description}", "cyan"))
    print_separator("=")
    print()

    # Print query and resource context
    print(colored("Query:", "yellow"), f'"{query.user_query}"')
    print(colored("Resource Context:", "yellow"))
    print(f"  - Kind: {query.resource.kind}")
    print(f"  - Name: {query.resource.name}")
    print(f"  - Namespace: {query.resource.namespace}")
    print()

    # Print agent response
    print_separator()
    print(colored("Agent Response:", "yellow"))
    print_separator()
    if query.actual_response:
        # Print response with proper formatting
        response_lines = query.actual_response.split('\n')
        for line in response_lines:
            print(line)
    else:
        print(colored("(No response received)", "red"))
    print()

    # Print expectation results
    if query.evaluation_result and query.evaluation_result.test_results:
        test_result = query.evaluation_result.test_results[0]

        # Count required vs optional expectations
        required_count = sum(1 for exp in query.expectations if exp.required)
        optional_count = len(query.expectations) - required_count

        print_separator()
        print(colored(f"Expectation Results ({len(query.expectations)} total, {required_count} required, {optional_count} optional):", "yellow"))
        print_separator()
        print()

        # Track pass/fail counts
        required_passed = 0
        required_total = 0
        optional_passed = 0
        optional_total = 0

        # Print each expectation with its result
        for expectation, metric_data in zip(query.expectations, test_result.metrics_data):
            # Determine if required or optional
            req_type = colored("[REQUIRED]", "red", attrs=["bold"]) if expectation.required else colored("[OPTIONAL]", "blue")

            # Get score and threshold
            score = metric_data.score
            threshold = expectation.threshold

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

            # Print statement with wrapping
            statement_lines = expectation.statement.split('\n')
            for i, line in enumerate(statement_lines):
                if i == 0:
                    print(f"   Statement: \"{line}\"")
                else:
                    print(f"              {line}")

            # Print result status
            if passed:
                if score < threshold + 0.1 and score > threshold:
                    # Borderline pass
                    print(colored(f"   Result: PASS (borderline!) - Score {score:.2f} just above threshold {threshold}", "yellow"))
                else:
                    print(colored(f"   Result: PASS", "green"))
            else:
                if score >= threshold - 0.1:
                    # Close to passing
                    print(colored(f"   Result: FAIL (close) - Score {score:.2f} just below threshold {threshold}", "yellow"))
                else:
                    print(colored(f"   Result: FAIL", "red"))

            # Print reason if available
            if hasattr(metric_data, 'reason') and metric_data.reason:
                reason_preview = metric_data.reason[:200]
                if len(metric_data.reason) > 200:
                    reason_preview += "..."
                print(f"   Reason: {reason_preview}")

            print()

        # Print summary
        print_separator()
        overall_passed = (required_passed == required_total)
        if overall_passed:
            summary_color = "green"
            status_icon = "✅"
            status_text = "TEST PASSED"
        else:
            summary_color = "red"
            status_icon = "❌"
            status_text = "TEST FAILED"

        # Check if any required expectations were borderline
        has_borderline = False
        for expectation, metric_data in zip(query.expectations, test_result.metrics_data):
            if expectation.required and metric_data.score < expectation.threshold + 0.1 and metric_data.score >= expectation.threshold:
                has_borderline = True
                break

        borderline_note = ""
        if has_borderline and overall_passed:
            borderline_note = colored(f"\n   ⚠️  Note: One or more required expectations passed with scores close to threshold", "yellow")

        print(colored(
            f"{status_icon} {status_text} (Required: {required_passed}/{required_total} | Optional: {optional_passed}/{optional_total}){borderline_note}",
            summary_color,
            attrs=["bold"]
        ))
        print_separator()
        print()


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


def print_test_results(scenario_list: ScenarioList, total_usage: int, time_taken: float) -> None:
    """Prints the test results."""
    print_header("Test Results:")
    print_results_per_scenario(scenario_list)
    print_retry_summary(scenario_list)
    print_response_times_summary()
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
    table.add_row(
        [
            "Initial Conversation",
            metrics.get_init_conversation_response_summary(),
        ]
    )
    table.add_row(
        [
            "Conversation",
            metrics.get_conversation_response_summary(),
        ]
    )
    print(table)


def print_token_usage(token_used: int) -> None:
    """Prints the token usage summary."""
    print_header(f"Total token used by evaluation tests: {token_used}")
