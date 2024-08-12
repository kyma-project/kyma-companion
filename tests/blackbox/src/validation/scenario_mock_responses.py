import os
from typing import List

import yaml
from pydantic import BaseModel

from common.logger import get_logger
from evaluation.scenario.scenario import Scenario

logger = get_logger(__name__)


class MockResponse(BaseModel):
    scenario_expectation_name: str
    expected_evaluation: bool


class ScenarioMockResponses(BaseModel):
    description: str
    scenario_id: str
    mock_response_content: str
    expected_evaluations: List[MockResponse]

    _scenario: Scenario

    @property
    def scenario(self):
        evaluation_data_dir = os.getenv("EVALUATION_DATA_PATH", "./data/evaluation")
        try:
            with open(f"{evaluation_data_dir}/namespace-scoped/{self.scenario_id}/scenario.yml") as file:
                scenario_yaml = yaml.safe_load(file)
        except FileNotFoundError:
            logger.error(f"Scenario file not found for scenario_id: {self.scenario_id}. "
                         f"Please check if this scenario file really exists.")
            raise
        return Scenario(**scenario_yaml)
