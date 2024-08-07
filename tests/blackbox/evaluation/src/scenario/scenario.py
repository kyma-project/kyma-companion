import json
import os
from logging import Logger

import yaml
from pydantic import BaseModel

from tests.blackbox.evaluation.src.scenario.enums import Category, Complexity
from tests.blackbox.evaluation.src.validator.evaluation import Evaluation


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
    categories: list[Category]
    complexity: Complexity


class Scenario(BaseModel):
    """Scenario is a class that contains the information of a Kyma common test scenario."""

    id: str
    description: str
    expectations: list[Expectation]
    evaluation: Evaluation = Evaluation()


class ScenarioList(BaseModel):
    """ScenarioDict is a list that contains scenarios."""

    items: list[Scenario] = []

    def add(self, item: Scenario) -> None:
        self.items.append(item)

    def load_all_namespace_scope_scenarios(self, path: str, logger: Logger) -> None:
        """Load all the scenarios from the namespace scoped test data path."""
        logger.info(f"Reading NamespaceScoped scenarios from: {path}")

        # get all the directories in the path.
        directories: list[str] = os.listdir(path)
        logger.info(f"Number of directories: {len(directories)}")

        # loop over all the directory names
        for dir_name in directories:
            scenario_file = path + "/" + dir_name + "/scenario.yaml"
            logger.debug(f"Loading scenario file: {scenario_file}")

            try:
                with open(scenario_file) as file:
                    scenario_yaml = yaml.load(file, Loader=yaml.FullLoader)
            except Exception as exception:
                raise Exception(
                    f"Error reading scenario file: {scenario_file}"
                ) from exception

            try:
                json_str = json.dumps(scenario_yaml)
                scenario = Scenario.model_validate_json(json_str)

                # add the scenario to the list.
                self.add(scenario)
            except Exception as exception:
                raise Exception(
                    f"Error parsing scenario file: {scenario_file}"
                ) from exception

        logger.info(f"Total scenarios loaded: {len(self.items)}")
