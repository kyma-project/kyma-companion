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


def print_test_results(
    scenario_list: ScenarioList, total_usage: int, time_taken: float
) -> None:
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
                print_header(
                    f"** Scenario ID: {scenario.id}, Query: {query.user_query}"
                )

                # print the response chunks.
                print_response_chunks(query.response_chunks)

                # print the evaluation results.
                if query.evaluation_result is not None:
                    for test_result in query.evaluation_result.test_results:
                        print_test_result(test_result, TestRunResultDisplay.ALL)

                # print the failure reason for the query.
                if query.test_status_reason != "":
                    print(
                        f"*** Query Status Reason: {colored(query.test_status_reason, 'red')}"
                    )

            # print failure reason for the scenario.
            if scenario.test_status_reason != "":
                print(
                    f"*** Scenario Status Reason: {colored(scenario.test_status_reason, 'red')}"
                )


def print_retry_summary(scenario_list: ScenarioList) -> None:
    """Prints summary of scenarios that required retries."""
    retried_scenarios = [s for s in scenario_list.items if s.attempt_number > 1]

    if len(retried_scenarios) == 0:
    if len(retried_scenarios) == 0:
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
        print(
            f"  - Scenario ID: {scenario.id} | Attempts: {scenario.attempt_number} | "
            f"Final Status: {status_text}"
        )
    print()
        )
    print()


def print_failed_queries(scenario_list: ScenarioList) -> None:
    """Prints the failed queries."""
    failed_queries = []
    for scenario in scenario_list.items:
        for query in scenario.queries:
            if query.test_status == TestStatus.FAILED:
                failed_queries.append(
                    f"Scenario ID: {scenario.id}, Query: {query.user_query}"
                )

    if len(failed_queries) == 0:
        return None

    print_header("List of failed test case:")
    for failed_query in failed_queries:
        print(colored(f"- {failed_query}", "red"))
    return None


def print_overall_results(scenario_list: ScenarioList) -> None:
    """Prints the overall results."""
    print_header(
        f"Overall success score across all expectations: {scenario_list.get_overall_success_rate()}%"
    )


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
