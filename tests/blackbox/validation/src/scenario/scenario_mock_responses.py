from typing import List

import yaml
from pydantic import BaseModel

from scenario.scenario import Scenario

COMPANION_FOLDER = "/Users/I504380/Go/src/github.com/muralov/kyma-companion"


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
        with open(f"{COMPANION_FOLDER}/tests/blackbox/data/evaluation/namespace-scoped/{self.scenario_id}/scenario.yml",
                  'r') as file:
            scenario_yaml = yaml.safe_load(file)
        return Scenario(**scenario_yaml)
