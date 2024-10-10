from evaluation.scenario.scenario import Expectation
from evaluation.scenario.scenario import Scenario as EvaluationScenario

from validation.scenario_mock_responses import ExpectedEvaluation


def string_to_bool(value: str) -> bool:
    """Convert a string to a boolean value."""
    if value.lower() in ["true", "1", "t", "y", "yes"]:
        return True
    if value.lower() in ["false", "0", "f", "n", "no"]:
        return False
    raise ValueError(f"{value} is not a valid boolean value.")


def print_seperator_line() -> None:
    """Print a line."""
    print("#########################################")


def get_expectation(
    eval_scenario: EvaluationScenario, expected_evaluation: ExpectedEvaluation
) -> Expectation | None:
    return next(
        (
            expectation
            for expectation in eval_scenario.expectations
            if expectation.name == expected_evaluation.scenario_expectation_name
        ),
        None,
    )
