import json

from deepeval.evaluate import print_test_result, aggregate_metric_pass_rates
from deepeval.test_run.test_run import TestRunResultDisplay
from evaluation.scenario.enums import TestStatus
from evaluation.scenario.scenario import ScenarioList
from prettytable import PrettyTable
from termcolor import colored

from common.metrics import Metrics
import github_action_utils as gha_utils


def print_header(name: str) -> None:
    print("\n************************************************************************")
    print(f"*** {name}")
    print("************************************************************************\n")


def colored_status(status: TestStatus) -> str:
    if status == TestStatus.PASSED:
        return colored(status.upper(), "green")
    elif status == TestStatus.FAILED:
        return colored(status.upper(), "red")
    elif status == TestStatus.COMPLETED:
        return colored(status.upper(), "blue")
    elif status == TestStatus.PENDING:
        return colored(status.upper(), "yellow")
    return colored(status.upper(), "red")


def print_test_results(scenario_list: ScenarioList, total_usage, time_taken) -> None:
    print_header("Test Results:")
    print_results_per_scenario(scenario_list)
    print_response_times_summary()
    print_token_usage(total_usage)
    print_header(f"Total time taken by evaluation tests: {time_taken} minutes.")
    # TODO: print list of failed queries.

def print_initial_questions(questions: list[str]) -> None:
    for i, q in enumerate(questions):
        print(f"\t{i + 1}: {q}")

def print_response_chunks(chunks: list) -> None:
    if len(chunks) == 0:
        return None
    print(json.dumps(chunks, indent=4))
    return None


def print_results_per_scenario(scenario_list: ScenarioList) -> None:
    for scenario in scenario_list.items:
        with gha_utils.group(f"Scenario ID: {scenario.id} (Test Status: {colored_status(scenario.test_status)})"):
            # print initial questions.
            print_header(f"* Scenario ID: {scenario.id}, Initial Questions:")
            print_initial_questions(scenario.initial_questions)

            # for each query print the evaluation results.
            for query in scenario.queries:
                print_header(f"** Scenario ID: {scenario.id}, Query: {query.user_query}")
                # print the response chunks.
                with gha_utils.group(f"Response chunks"):
                    print_response_chunks(query.response_chunks)
                # print the evaluation results.
                if query.evaluation_result is not None:
                    for test_result in query.evaluation_result.test_results:
                        print_test_result(test_result, TestRunResultDisplay.ALL)
                # print the failure reason.
                if query.test_status_reason != "":
                    print(
                        f"*** Query Status Reason: {colored(query.test_status_reason, 'red')}"
                    )
            # print failure reason.
            if scenario.test_status_reason != "":
                print(
                    f"*** Scenario Status Reason: {colored(scenario.test_status_reason, 'red')}"
                )


def print_response_times_summary() -> None:
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
    print_header(f"Total token used by evaluation tests: {token_used}")
