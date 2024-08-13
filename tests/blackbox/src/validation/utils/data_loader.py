import os

import yaml
from common.logger import get_logger

from validation.scenario_mock_responses import ScenarioMockResponses

logger = get_logger(__name__)


def load_data(data_dir) -> list[ScenarioMockResponses]:
    results: list[ScenarioMockResponses] = []
    logger.info(f"Loading validation data from the directory: {data_dir}")
    try:
        for filename in os.listdir(data_dir):
            if filename.endswith((".yaml", ".yml")):
                file_path = os.path.join(data_dir, filename)
                with open(file_path) as file:
                    yaml_data = yaml.safe_load(file)
                    mock_response = ScenarioMockResponses(**yaml_data)
                    results.append(mock_response)
    except Exception:
        logger.exception(
            f"Failed to load validation data from the directory: {data_dir}"
        )
        raise

    return results
