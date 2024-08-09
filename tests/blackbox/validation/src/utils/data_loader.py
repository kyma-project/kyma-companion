import os
from typing import List

import yaml

from validation.scenario_mock_responses import ScenarioMockResponses


def load_data(data_dir) -> List[ScenarioMockResponses]:
    results: List[ScenarioMockResponses] = []
    for filename in os.listdir(data_dir):
        if filename.endswith(('.yaml', '.yml')):
            file_path = os.path.join(data_dir, filename)

            with open(file_path) as file:
                # Load the YAML content
                yaml_data = yaml.safe_load(file)

                mock_response = ScenarioMockResponses(**yaml_data)
                results.append(mock_response)

    return results
