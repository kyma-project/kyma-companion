import os
from typing import List

import yaml
from pydantic import BaseModel

from scenario.scenario import Scenario


class MockResponse(BaseModel):
    scenario_expectation_name: str
    expected_evaluation: bool


class ScenarioMockResponses(BaseModel):
    id: str
    description: str
    scenario_id: str
    mock_response_content: str
    expected_evaluations: List[MockResponse]

    _scenario: Scenario

    @property
    def scenario(self):
        evaluation_data_dir = os.getenv("EVALUATION_DATA_DIR", "./tests/blackbox/data/evaluation")
        with open(f"{evaluation_data_dir}/namespace-scoped/{self.scenario_id}/scenario.yml",
                  'r') as file:
            scenario_yaml = yaml.safe_load(file)
        return Scenario(**scenario_yaml)
