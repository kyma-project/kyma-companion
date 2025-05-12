import json
import os
from logging import Logger

import yaml
from deepeval.evaluate import EvaluationResult
from pydantic import BaseModel

from evaluation.scenario.enums import (
    TestStatus,
)

PASSING_SCORE = 100


class Resource(BaseModel):
    """
    Resource represents a K8s resource.
    """

    kind: str
    api_version: str
    name: str
    namespace: str


class Expectation(BaseModel):
    """
    Expectation represents a single expectation with a statement and an optional expected response.
    """

    name: str
    statement: str
    threshold: float = 0.5


class Query(BaseModel):
    """Query represents a single test scenario with an id, description"""
    user_query: str
    resource: Resource
    expectations: list[Expectation]
    # actual responses
    response_chunks: list = []
    actual_response: str = ""
    # evaluation
    test_status: TestStatus = TestStatus.PENDING
    test_status_reason: str = ""
    evaluation_result: EvaluationResult | None = None

    def complete(self) -> None:
        # map the evaluation result to the individual expectations.
        if self.test_status != TestStatus.PENDING and self.evaluation_result is not None:
            self.evaluation.status = TestStatus.COMPLETED
            for test_result in self.evaluation_result.test_results:
                if not test_result.success:
                    self.test_status = TestStatus.FAILED
                    break


class Scenario(BaseModel):
    """Scenario is a class that contains the information of a Kyma companion test scenario."""

    id: str
    description: str
    queries: list[Query] = []
    # actual responses
    initial_questions: list[str] = []
    # evaluation
    test_status: TestStatus = TestStatus.PENDING
    test_status_reason: str = ""

    def complete(self) -> None:
        if self.test_status != TestStatus.FAILED:
            self.test_status = TestStatus.COMPLETED
            for query in self.queries:
                query.complete()
                if query.test_status == TestStatus.FAILED:
                    self.test_status = TestStatus.FAILED
                    break


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
            scenario_file = path + "/" + dir_name + "/scenario.yml"
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

    def is_test_passed(self) -> bool:
        """Get the overall success across all scenarios."""
        for scenario in self.items:
            if scenario.test_status == TestStatus.FAILED:
                return False
        return True
