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

    def get_scenario_score(self) -> float:
        return self.evaluation.get_scenario_score(self.expectations)

    def complete(self) -> None:
        if self.evaluation.status == TestStatus.FAILED:
            return

        # COMPLETED means that the test is completed but with score < 100%.
        self.evaluation.status = TestStatus.COMPLETED
        # if the scenario score is 100, the scenario is passed.
        if self.get_scenario_score() == PASSING_SCORE:
            self.evaluation.status = TestStatus.PASSED



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


class ScenarioList(BaseModel):
    """ScenarioDict is a list that contains scenarios."""

    items: list[Scenario] = []

    def add(self, item: Scenario) -> None:
        self.items.append(item)

    def get_overall_success_rate(self) -> float:
        """Get the overall success rate (%) across all expectations."""
        success_count: int = 0
        count: int = 0

        for item in self.items:
            for expectation in item.expectations:
                success_count += expectation.get_success_count()
                count += expectation.get_results_count()

        if count == 0:
            return 0.0
        return round(float((success_count / count) * 100), 2)

    def get_failed_scenarios(self) -> list[Scenario]:
        """Get the list of failed scenarios."""
        failed_scenarios: list[Scenario] = []
        for item in self.items:
            if item.evaluation.status == TestStatus.FAILED:
                failed_scenarios.append(item)
        return failed_scenarios

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

    def is_test_passed(self) -> tuple[bool, str]:
        """Get the overall success across all scenarios."""
        # if the overall success rate is 0.0, return False.
        if self.get_overall_success_rate() == 0.0:
            return False, "The overall success rate is 0.0"

        return True, "All tests passed successfully"

    def is_test_failed(self) -> bool:
        """Check if any of the scenarios failed."""
        failed_scenarios = self.get_failed_scenarios()
        return len(failed_scenarios) > 0
