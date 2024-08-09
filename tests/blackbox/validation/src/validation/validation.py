import os
from typing import List

import yaml

from scenario.scenario_mock_responses import ScenarioMockResponses
from validation.validator import Validator, ModelValidator

COMPANION_FOLDER = "/Users/I504380/Go/src/github.com/muralov/kyma-companion"


class Validation:
    validator: Validator
    llms = []
    mock_responses: List[ScenarioMockResponses]

    def __init__(self, llms):
        self.llms = llms
        self.mock_responses = self._load_data()
        self.validator = ModelValidator()

    def _load_data(self) -> List[ScenarioMockResponses]:
        results: List[ScenarioMockResponses] = []
        directory = f"{COMPANION_FOLDER}/tests/blackbox/data/validation/scenario_mock_responses/"
        for filename in os.listdir(directory):
            if filename.endswith(('.yaml', '.yml')):
                file_path = os.path.join(directory, filename)

                with open(file_path) as file:
                    # Load the YAML content
                    yaml_data = yaml.safe_load(file)

                    # Use the filename (without extension) as the key
                    # key = os.path.splitext(filename)[0]
                    # yaml_data[key] = data
                    mock_response = ScenarioMockResponses(**yaml_data)
                    results.append(mock_response)

        return results

    # TODO: this should start a new coroutine per model
    def validate(self):
        # loop over all the models
        model_scores = {}
        for llm in self.llms:
            print("Validating model: ", self.llms)
            score = self.validator.validate(self.mock_responses, llm)
            model_scores[llm.model_name] = score

        print("Model scores: ", model_scores)
