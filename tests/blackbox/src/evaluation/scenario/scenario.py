import json
import os
from logging import Logger

import yaml
from deepeval.evaluate import EvaluationResult, TestResult
from pydantic import BaseModel

from evaluation.companion.response_models import ConversationResponseChunk
from evaluation.scenario.enums import (
    TestStatus,
)

REQUIRED_METRIC_PREFIX = "required"


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
    required: bool = True

    def get_deepeval_metric_name(self) -> str:
        """
        Get the deepeval metric name for the expectation.
        """
        return f"{REQUIRED_METRIC_PREFIX}_{self.name}" if self.required else self.name


class Query(BaseModel):
    """Query represents a single test scenario with an id, description"""

    user_query: str
    resource: Resource
    expectations: list[Expectation]
    # actual responses
    response_chunks: list[ConversationResponseChunk] = []
    actual_response: str = ""
    # evaluation
    test_status: TestStatus = TestStatus.PENDING
    test_status_reason: str = ""
    evaluation_result: EvaluationResult | None = None

    def complete(self) -> None:
        """Update the test status based on the evaluation result."""
        if self.test_status != TestStatus.FAILED:
            if self.evaluation_result is None:
                self.test_status = TestStatus.FAILED
                self.test_status_reason = "Evaluation result is None"
                return
            # if any of the critical expectations are not met, we fail the test.
            self.test_status = TestStatus.COMPLETED
            for test_result in self.evaluation_result.test_results:
                if not self.__is_test_successful(test_result):
                    self.test_status = TestStatus.FAILED
                    break

    def __is_test_successful(self, result: TestResult) -> bool:
        """
        It will only fail the test if the critical expectations are not met.
        """
        if result.metrics_data is None:
            return False
        for test_metric in result.metrics_data:
            if (
                test_metric.name.startswith(REQUIRED_METRIC_PREFIX)
                and not test_metric.success
            ):
                return False
        return True


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
        """Update the test status based on the evaluation result."""
        if self.test_status != TestStatus.FAILED:
            self.test_status = TestStatus.COMPLETED
            for query in self.queries:
                query.complete()
                if query.test_status == TestStatus.FAILED:
                    self.test_status = TestStatus.FAILED
                    # we do not break here because we want to update the status of all queries.


class ScenarioList(BaseModel):
    """ScenarioDict is a list that contains scenarios."""

    items: list[Scenario] = []

    def add(self, item: Scenario) -> None:
        """Add a scenario to the list."""
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

    def get_overall_success_rate(self) -> float:
        """Get the overall success rate (%) across all expectations."""
        score: float = 0.0
        total: float = 0.0

        for item in self.items:
            for query in item.queries:
                total += len(query.expectations)
                if query.evaluation_result is not None:
                    for test_result in query.evaluation_result.test_results:
                        for test_metric in test_result.metrics_data:
                            score += test_metric.score

        if total == 0:
            return 0.0
        return round(float((score / total) * 100), 2)

    def is_test_passed(self) -> bool:
        """Get the overall success across all scenarios."""
        return all(scenario.test_status != TestStatus.FAILED for scenario in self.items)
