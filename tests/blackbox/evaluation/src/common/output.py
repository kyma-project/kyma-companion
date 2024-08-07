from tests.blackbox.evaluation.src.scenario.enums import TestStatus
from tests.blackbox.evaluation.src.scenario.scenario import ScenarioList
from prettytable import PrettyTable


def print_header(name: str) -> None:
    print("\n************************************************************************")
    print(f"*** {name}")
    print("************************************************************************\n")


def print_test_results(scenario_list: ScenarioList) -> None:
    print_failed_expectations(scenario_list)
    print_tabular_results(scenario_list)
    print_overall_outcome(scenario_list)


def print_tabular_results(scenario_list: ScenarioList) -> None:
    table = PrettyTable()
    table.field_names = ["Status", "Weighted Mean Score", "Standard Deviation Score", "Scenario ID", "Description"]

    print_header("Test Results:")
    for scenario in scenario_list.items:
        table.add_row([
            scenario.evaluation.status.upper(),
            scenario.evaluation.mean_weighted_performance,
            scenario.evaluation.standard_deviation,
            scenario.id,
            scenario.description])

    print(table)


def print_failed_expectations(scenario_list: ScenarioList) -> None:
    print_header("List of failed expectations:")
    for scenario in scenario_list.items:
        if scenario.evaluation.status == TestStatus.FAILED:
            print(f"* Scenario ID: {scenario.id}, Description: {scenario.description}")
            print(f"\t Actual response: {scenario.evaluation.actual_response}")

            print(f"\t Failed expectations:")
            for expectation in scenario.evaluation.expectations_result:
                if not expectation.success:
                    print(f"\t\t x Expectation: {expectation.expectation_name}")
            print("\n")


def print_overall_outcome(scenario_list: ScenarioList) -> None:
    test_passed = TestStatus.PASSED
    for scenario in scenario_list.items:
        if scenario.evaluation.status == TestStatus.FAILED:
            test_passed = TestStatus.FAILED
            break

    print_header(f"Test Outcome: {test_passed.upper()}")
