import json
import os
from logging import Logger

import yaml
from pydantic import BaseModel

from tests.blackbox.evaluation.src.scenario.enums import Category, Complexity, TestStatus


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
    results: list[bool] = []

    def add_result(self, result: bool) -> None:
        """Add a new expectation result to the list."""
        self.results.append(result)

    def get_success_count(self) -> int:
        """Get the number of successful results."""
        total_success: int = 0
        for result in self.results:
            total_success += int(result)
        return total_success

    def get_results_count(self) -> int:
        """Get the number of results."""
        return len(self.results)

    def get_success_rate(self) -> float:
        """Get the success rate (%) of the expectation results."""
        if self.get_results_count() == 0:
            return 0.0
        score = (self.get_success_count() / self.get_results_count()) * 100
        return round(score, 2)


class Evaluation(BaseModel):
    """Evaluation is a class that contains the information of a scenario evaluation results."""

    status: TestStatus = TestStatus.PENDING
    status_reason: str = ""
    actual_responses: list[str] = []

    def add_actual_response(self, response: str) -> None:
        """Add a new expectation result to the list."""
        self.actual_responses.append(response)

    def get_scenario_score(self, expectations: list[Expectation]) -> float:
        """Get the scenario score considering the complexity of expectations."""

        # calculate the weighted mean of the scenario from all expectation considering the complexity.
        actual_sum: int = 0
        ideal_sum: int = 0
        count: int = 0
        for expectation in expectations:
            actual_sum += expectation.get_success_count() * expectation.complexity.to_int()
            # ideal sum is the sum when all the results would be successful.
            ideal_sum += expectation.get_results_count() * expectation.complexity.to_int()
            count += expectation.get_results_count()

        if count == 0:
            return 0.0

        mean_weighted_performance: float = float(actual_sum / count)
        # ideal_weighted_performance sum is the performance when all the results would be successful.
        ideal_weighted_performance: float = float(ideal_sum / count)
        score = (mean_weighted_performance / ideal_weighted_performance) * 100
        return round(score, 2)


class Scenario(BaseModel):
    """Scenario is a class that contains the information of a Kyma companion test scenario."""

    id: str
    description: str
    expectations: list[Expectation]
    evaluation: Evaluation = Evaluation()

    def get_scenario_score(self) -> float:
        return self.evaluation.get_scenario_score(self.expectations)

    def complete(self) -> None:
        if self.evaluation.status == TestStatus.FAILED:
            return

        self.evaluation.status = TestStatus.COMPLETED
        # if the scenario score is 100, the scenario is passed.
        if self.get_scenario_score() == 100:
            self.evaluation.status = TestStatus.PASSED


class ScenarioList(BaseModel):
    """ScenarioDict is a list that contains scenarios."""

    items: list[Scenario] = []

    def add(self, item: Scenario) -> None:
        self.items.append(item)

    def get_success_rate_per_category(self) -> dict[Category, float]:
        """Get the success rate (%) per category across all expectations."""
        success_count: dict[Category, int] = {}
        total_count: dict[Category, int] = {}

        for item in self.items:
            for expectation in item.expectations:
                for category in expectation.categories:
                    if category not in success_count:
                        success_count[category] = expectation.get_success_count()
                    else:
                        success_count[category] += expectation.get_success_count()

                    if category not in total_count:
                        total_count[category] = expectation.get_results_count()
                    else:
                        total_count[category] += expectation.get_results_count()

        success_rate: dict[Category, float] = {}
        for category in success_count:
            if total_count[category] == 0:
                success_rate[category] = 0.0
            else:
                success_rate[category] = round(float((success_count[category] / total_count[category]) * 100), 2)

        return success_rate

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
