from prettytable import PrettyTable
from termcolor import colored

from tests.blackbox.evaluation.src.scenario.enums import TestStatus
from tests.blackbox.evaluation.src.scenario.scenario import ScenarioList


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
    raise ValueError(f"Unknown status: {status}")


def print_test_results(scenario_list: ScenarioList) -> None:
    print_results_per_scenario(scenario_list)
    print_results_per_category(scenario_list)
    print_overall_results(scenario_list)


def print_results_per_category(scenario_list: ScenarioList) -> None:
    table = PrettyTable()
    table.field_names = [
        "Category Name",
        "Score (%)",
    ]

    print_header("Test Results per Category:")
    success_rate_per_category = scenario_list.get_success_rate_per_category()
    for category, score in success_rate_per_category.items():
        table.add_row(
            [
                category,
                score,
            ]
        )

    print(table)


def print_results_per_scenario(scenario_list: ScenarioList) -> None:
    print_header("Test Scenarios:")
    for scenario in scenario_list.items:
        print(f"* Scenario ID: {scenario.id}, Description: {scenario.description}")
        print(f"\t Status: {colored_status(scenario.evaluation.status)}")
        if scenario.evaluation.status_reason != "":
            print(f"\t Status reason: {scenario.evaluation.status_reason}")

        print("\t Expectations:")
        for expectation in scenario.expectations:
            print(
                f"\t\t - [SUCCESS RATE: {expectation.get_success_rate()}%] Expectation: {expectation.name}"
            )
        print(f"\t Scenario score: {scenario.get_scenario_score()}%")
        print("\n")


def print_overall_results(scenario_list: ScenarioList) -> None:
    print_header(
        f"Overall success score across all expectations: {scenario_list.get_overall_success_rate()}%"
    )
