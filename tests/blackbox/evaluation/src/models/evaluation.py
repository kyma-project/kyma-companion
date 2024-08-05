import math
from pydantic import BaseModel
from typing import List

from tests.blackbox.evaluation.src.models.enums import Complexity, TestStatus


class ExpectationResult(BaseModel):
    """ExpectationResult is a class that stores the result of comparing
    an expectation with the assistant_response."""

    expectation_name: str
    success: bool


class Evaluation(BaseModel):
    """Evaluation is a class that contains the information of a scenario evaluation results."""

    status: TestStatus = TestStatus.PENDING
    status_reason: str = ""
    actual_response: str = ""
    expectations_result: List[ExpectationResult] = []
    mean_weighted_performance: float = 0.0
    standard_deviation: float = 0.0

    def add_expectation_result(self, expectation_name: str, success: bool) -> None:
        """Add a new expectation result to the list."""
        self.expectations_result.append(
            ExpectationResult(
                expectation_name=expectation_name,
                success=success,
            )
        )

    def compute_status(self) -> None:
        if self.status == TestStatus.FAILED:
            return

        if len(self.expectations_result) == 0:
            self.status = TestStatus.FAILED
            self.status_reason = "No expectations were evaluated."
            return

        # by default, the test is passed.
        self.status = TestStatus.PASSED

        # if any expectation failed, the test is failed.
        # traverse all the results and append all failed expectation names
        for result in self.expectations_result:
            if not result.success:
                self.status = TestStatus.FAILED
                self.status_reason += f"Expectation {result.expectation_name} failed.\n"

    def compute_mean_weighted_performance(self, complexity: Complexity) -> float:
        total_sum: float = 0.0
        for result in self.expectations_result:
            total_sum += int(result.success) * complexity.to_int()

        self.mean_weighted_performance = total_sum / len(self.expectations_result)
        return self.mean_weighted_performance

    def compute_standard_deviation(self, complexity: Complexity) -> float:
        mean = self.compute_mean_weighted_performance(complexity)
        total_sum: float = 0.0
        for result in self.expectations_result:
            total_sum += math.pow(int(result.success) - mean, 2)

        self.standard_deviation = math.pow(total_sum / len(self.expectations_result), 0.5)
        return self.standard_deviation
