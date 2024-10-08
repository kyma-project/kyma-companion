import os

import yaml
from common.logger import get_logger
from evaluation.scenario.scenario import Scenario as EvaluationScenario

from validation.scenario_mock_responses import MockResponse, ValidationScenario

logger = get_logger(__name__)


def load_data(data_dir: str) -> list[ValidationScenario]:
    # Load the validation data from the given directory. The directory should contain subdirectories with the given
    # scenarios. Each scenario should have a validation.yml file containing the mock responses for the scenario and
    # an evaluation.yml file containing the scenario details.
    logger.info(f"Loading validation data from the directory: {data_dir}")

    results: list[ValidationScenario] = []
    try:
        for subdir in os.listdir(data_dir):
            subdir_path = os.path.join(data_dir, subdir)
            if os.path.isdir(subdir_path):
                validation_file_path = os.path.join(subdir_path, "validation.yml")
                evaluation_file_path = os.path.join(subdir_path, "evaluation.yml")

                # Load the Scenario from the evaluation file.
                logger.info(f"Loading evaluation data from {evaluation_file_path}")
                scenario: EvaluationScenario
                if os.path.exists(evaluation_file_path):
                    with open(evaluation_file_path) as eval_file:
                        eval_data = yaml.safe_load(eval_file)
                        scenario = EvaluationScenario(**eval_data)
                else:
                    logger.error(f"Evaluation data not found at {evaluation_file_path}")
                    raise FileNotFoundError(
                        f"Evaluation data not found for the scenario: {subdir}"
                    )

                # Load the mock responses for the given scenario from the validation file.
                logger.info(f"Loading validation data from {validation_file_path}")
                mock_responses: list[MockResponse] = []
                if os.path.exists(validation_file_path):
                    with open(validation_file_path) as val_file:
                        val_data = yaml.safe_load(val_file)
                        mock_responses = [MockResponse(**data) for data in val_data]
                else:
                    logger.error(f"Validation data not found at {validation_file_path}")
                    raise FileNotFoundError(
                        f"Validation data not found for the scenario: {subdir}"
                    )

                # Build the validation scenario from the scenario and the corresponding mock responses.
                validation_scenario = ValidationScenario(
                    eval_scenario=scenario, mock_responses=mock_responses
                )
                results.append(validation_scenario)
                logger.info(
                    f"Loaded data for scenario '{validation_scenario.eval_scenario.id}' "
                    f"with {len(validation_scenario.mock_responses)} mock responses"
                )
    except Exception:
        logger.exception(
            f"Failed to load validation data from the directory: {data_dir}"
        )
        raise

    logger.info(f"loaded data from {len(results)} scenarios")
    return results
