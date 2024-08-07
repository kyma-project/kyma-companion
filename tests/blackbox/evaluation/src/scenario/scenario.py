import os
import yaml
import json
from typing import List

from pydantic import BaseModel
from logging import Logger

from tests.blackbox.evaluation.src.validator.evaluation import Evaluation
from tests.blackbox.evaluation.src.scenario.enums import Complexity, Category


class Resource(BaseModel):
    """
    Resource represents a K8s resource.
    """

    type: str
    name: str
    namespace: str


class Expectation(BaseModel):
    """
    Expectation represents a single expectation with a statement, a list of categories,
    a description, and a complexity.
    """

    name: str
    statement: str
    categories: List[Category]
    complexity: Complexity


class Scenario(BaseModel):
    """Scenario is a class that contains the information of a Kyma common test scenario."""

    id: str
    description: str
    expectations: List[Expectation]
    evaluation: Evaluation = Evaluation()


class ScenarioList(BaseModel):
    """ScenarioDict is a list that contains scenarios."""

    items: List[Scenario] = []

    def add(self, item: Scenario) -> None:
        self.items.append(item)

    def load_all_namespace_scope_scenarios(self, path: str, logger: Logger) -> None:
        """Load all the scenarios from the namespace scoped test data path."""
        logger.info(f"Reading NamespaceScoped scenarios from: {path}")

        # get all the directories in the path.
        directories: List[str] = os.listdir(path)
        logger.info(f"Number of directories: {len(directories)}")

        # loop over all the directory names
        for dir_name in directories:
            scenario_file = path + "/" + dir_name + "/scenario.yaml"
            logger.info(f"Loading scenario file: {scenario_file}")

            try:
                with open(scenario_file, "r") as file:
                    scenario_yaml = yaml.load(file, Loader=yaml.FullLoader)
            except Exception as e:
                raise Exception(f"Error reading scenario file: {scenario_file}", e)

            try:
                json_str = json.dumps(scenario_yaml)
                scenario = Scenario.model_validate_json(json_str)

                # add the scenario to the list.
                self.add(scenario)
            except Exception as e:
                raise Exception(f"Error parsing scenario file: {scenario_file}", e)

        logger.info(f"Total scenarios loaded: {len(self.items)}")
