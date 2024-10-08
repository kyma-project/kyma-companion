from validation.scenario_mock_responses import ValidationScenario
from validation.utils.data_loader import load_data
from validation.utils.utils import get_expectation

# Unit tests run from the rootdir of the repository.
DEFAULT_DATA_DIR: str = "tests/blackbox/data/namespace-scoped"


def test_data_integrity():
    validation_scenarios: list[ValidationScenario] = load_data(DEFAULT_DATA_DIR)
    for scenario in validation_scenarios:
        for mock_response in scenario.mock_responses:
            for expected_evaluation in mock_response.expected_evaluations:
                expectation = get_expectation(
                    scenario.eval_scenario, expected_evaluation
                )
                assert expectation is not None, (
                    f"For scenario {scenario.eval_scenario.id} and mock response "
                    f"{mock_response.description} expected evaluation "
                    f"{expected_evaluation.scenario_expectation_name} not found"
                )
