"""Main is to demo the mock assistant, evaluate its responses, and calibrate it."""
# load env vars from .env file
from dotenv import load_dotenv

load_dotenv()

from src.data.fixtures_calibration import ALL_CALIBRATIONS as CALIBRATIONS
from src.data.fixtures_scenarios import LATEST_SCENARIOS as SCENARIOS
from src.logic.chat_models import get_gpt35_model, get_gpt4o_model
from src.logic.evaluate import evaluate_scenario
from src.logic.mock_assistant import get_response_for_scenario
from src.logic.utils import print_seperator_line
from src.logic.validate import validate


def main():
    """Main function to evaluate the model's responses to the given scenarios."""

    # Get response for all scenarios via the mock assistant.
    print("Getting responses for all scenarios.")
    scenarios = SCENARIOS
    for scenario in scenarios.items:
        mock_assistant = get_gpt35_model()
        get_response_for_scenario(mock_assistant, scenario)

    # Evaluate the responses against the expectations.
    print("Evaluate response for all scenarios.")
    for scenario in scenarios.items:
        evaluating_model = get_gpt4o_model()
        evaluate_scenario(scenario, evaluating_model)

    # Print the results of the Evaluation.
    scenarios.print_scores_by_category()
    scenarios.print_scores_by_scenario()

    # Calibrate the model that is used to evaluate the responses.
    # todo, this should be named validation.
    calibrations = CALIBRATIONS
    for calibration in calibrations:
        calibrating_model = get_gpt4o_model()
        validate(calibration, calibrating_model)

        print_seperator_line()
        print(
            f"Results per category for calibration {calibration.scenario.scenario_id}:"
        )
        calibration.print_score_per_category()
        print_seperator_line()
        print(
            f"Results per mock response for calibration {calibration.scenario.scenario_id}:"
        )
        calibration.print_score_per_mock_response()


if __name__ == "__main__":
    main()
