import json
import os
from logging import Logger

import yaml
from deepeval.evaluate.types import EvaluationResult, TestResult
from pydantic import BaseModel, Field

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
    api_version: str = ""
    name: str = ""
    namespace: str = ""


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


class QueryMetrics(BaseModel):
    """Per-query performance and cost metrics collected during evaluation."""

    # timing (seconds)
    latency_seconds: float = 0.0
    evaluation_latency_seconds: float = 0.0
    # token usage (this query only, reported by the server)
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    # agent behaviour
    llm_call_count: int = 0
    tool_calls: list[str] = Field(default_factory=list)
    tool_call_count: int = 0
    tool_call_counts: dict[str, int] = Field(default_factory=dict)
    # response shape
    response_char_count: int = 0
    response_word_count: int = 0

    def apply_server_metrics(self, server_metrics: dict) -> None:
        """Populate token/tool/LLM metrics from the server-reported metrics dict."""
        if not server_metrics:
            return
        self.input_tokens = int(server_metrics.get("input_tokens", 0) or 0)
        self.output_tokens = int(server_metrics.get("output_tokens", 0) or 0)
        self.total_tokens = int(server_metrics.get("total_tokens", 0) or 0)
        self.llm_call_count = int(server_metrics.get("llm_call_count", 0) or 0)
        self.tool_calls = list(server_metrics.get("tool_calls", []) or [])
        self.tool_call_count = int(server_metrics.get("tool_call_count", len(self.tool_calls)) or 0)
        self.tool_call_counts = dict(server_metrics.get("tool_call_counts", {}) or {})

    def set_response_shape(self, response: str) -> None:
        """Compute response size metrics from the answer text."""
        self.response_char_count = len(response)
        self.response_word_count = len(response.split())


class Query(BaseModel):
    """Query represents a single test scenario with an id, description"""

    user_query: str
    resource: Resource
    expectations: list[Expectation]
    # actual responses
    response_chunks: list[ConversationResponseChunk] = []
    actual_response: str = ""
    # per-query performance metrics
    metrics: QueryMetrics = Field(default_factory=QueryMetrics)
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
            if test_metric.name.startswith(REQUIRED_METRIC_PREFIX) and not test_metric.success:
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
    # retry tracking
    attempt_number: int = 0
    attempt_history: list[dict] = Field(default_factory=list)

    def reset(self) -> None:
        """Reset scenario state for retry attempts."""
        self.test_status = TestStatus.PENDING
        self.test_status_reason = ""
        self.initial_questions = []
        for query in self.queries:
            query.test_status = TestStatus.PENDING
            query.test_status_reason = ""
            query.actual_response = ""
            query.response_chunks = []
            query.evaluation_result = None
            query.metrics = QueryMetrics()

    def record_attempt_history(self, attempt: int) -> None:
        """Record metrics for the current attempt in attempt_history."""
        queries_passed = sum(1 for q in self.queries if q.test_status in [TestStatus.COMPLETED, TestStatus.PASSED])
        queries_failed = sum(1 for q in self.queries if q.test_status == TestStatus.FAILED)
        queries_pending = sum(1 for q in self.queries if q.test_status == TestStatus.PENDING)
        self.attempt_history.append(
            {
                "attempt": attempt,
                "status": self.test_status.value,
                "reason": self.test_status_reason,
                "queries_passed": queries_passed,
                "queries_failed": queries_failed,
                "queries_pending": queries_pending,
            }
        )

    def complete(self) -> None:
        """Update the test status based on the evaluation result."""
        if self.test_status != TestStatus.FAILED:
            self.test_status = TestStatus.COMPLETED
            for query in self.queries:
                query.complete()
                if query.test_status == TestStatus.FAILED:
                    self.test_status = TestStatus.FAILED
                    # we do not break here because we want to update the status of all queries.

    def aggregate_metrics(self) -> dict:
        """Aggregate per-query metrics into scenario-level totals and averages."""
        num_queries = len(self.queries)
        tool_call_counts: dict[str, int] = {}
        for query in self.queries:
            for name, count in query.metrics.tool_call_counts.items():
                tool_call_counts[name] = tool_call_counts.get(name, 0) + count

        total_latency = sum(q.metrics.latency_seconds for q in self.queries)
        total_eval_latency = sum(q.metrics.evaluation_latency_seconds for q in self.queries)
        total_input = sum(q.metrics.input_tokens for q in self.queries)
        total_output = sum(q.metrics.output_tokens for q in self.queries)
        total_tokens = sum(q.metrics.total_tokens for q in self.queries)
        total_llm_calls = sum(q.metrics.llm_call_count for q in self.queries)
        total_tool_calls = sum(q.metrics.tool_call_count for q in self.queries)

        return {
            "scenario_id": self.id,
            "status": self.test_status.value,
            "attempts": self.attempt_number,
            "num_queries": num_queries,
            "total_latency_seconds": round(total_latency, 4),
            "avg_latency_seconds": round(total_latency / num_queries, 4) if num_queries else 0.0,
            "total_evaluation_latency_seconds": round(total_eval_latency, 4),
            "input_tokens": total_input,
            "output_tokens": total_output,
            "total_tokens": total_tokens,
            "avg_tokens_per_query": round(total_tokens / num_queries, 2) if num_queries else 0.0,
            "llm_call_count": total_llm_calls,
            "tool_call_count": total_tool_calls,
            "tool_call_counts": tool_call_counts,
        }


class ScenarioList(BaseModel):
    """ScenarioDict is a list that contains scenarios."""

    items: list[Scenario] = []

    def add(self, item: Scenario) -> None:
        """Add a scenario to the list."""
        self.items.append(item)

    def load_all_namespace_scope_scenarios(self, path: str, logger: Logger) -> None:
        """Load all the scenarios from the namespace scoped test data path."""
        logger.info(f"Reading NamespaceScoped scenarios from: {path}")

        # get all the directories in the path (skip plain files like deploy_all.sh).
        directories: list[str] = [entry for entry in os.listdir(path) if os.path.isdir(os.path.join(path, entry))]
        if directories:
            # sort directories to ensure consistent order
            directories.sort(reverse=True)
        logger.info(f"Number of directories: {len(directories)}")

        # loop over all the directory names
        for dir_name in directories:
            scenario_file = path + "/" + dir_name + "/scenario.yml"
            logger.debug(f"Loading scenario file: {scenario_file}")

            try:
                with open(scenario_file) as file:
                    scenario_yaml = yaml.load(file, Loader=yaml.FullLoader)
            except Exception as exception:
                raise Exception(f"Error reading scenario file: {scenario_file}") from exception

            try:
                json_str = json.dumps(scenario_yaml)
                scenario = Scenario.model_validate_json(json_str)

                # add the scenario to the list.
                self.add(scenario)
            except Exception as exception:
                raise Exception(f"Error parsing scenario file: {scenario_file}") from exception

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
                        if test_result.metrics_data:
                            for test_metric in test_result.metrics_data:
                                score += test_metric.score if test_metric.score else 0.0

        if total == 0:
            return 0.0
        return round(float((score / total) * 100), 2)

    def is_test_passed(self) -> bool:
        """Get the overall success across all scenarios."""
        return all(scenario.test_status != TestStatus.FAILED for scenario in self.items)

    def build_metrics_report(self) -> dict:
        """Build a machine-readable metrics report across all scenarios and queries."""
        scenarios = [scenario.aggregate_metrics() for scenario in self.items]

        run_tool_counts: dict[str, int] = {}
        for scenario in scenarios:
            for name, count in scenario["tool_call_counts"].items():
                run_tool_counts[name] = run_tool_counts.get(name, 0) + count

        num_queries = sum(s["num_queries"] for s in scenarios)
        total_tokens = sum(s["total_tokens"] for s in scenarios)
        total_latency = sum(s["total_latency_seconds"] for s in scenarios)

        return {
            "summary": {
                "num_scenarios": len(scenarios),
                "num_queries": num_queries,
                "overall_success_rate": self.get_overall_success_rate(),
                "input_tokens": sum(s["input_tokens"] for s in scenarios),
                "output_tokens": sum(s["output_tokens"] for s in scenarios),
                "total_tokens": total_tokens,
                "avg_tokens_per_query": round(total_tokens / num_queries, 2) if num_queries else 0.0,
                "total_latency_seconds": round(total_latency, 4),
                "avg_latency_seconds": round(total_latency / num_queries, 4) if num_queries else 0.0,
                "total_llm_call_count": sum(s["llm_call_count"] for s in scenarios),
                "total_tool_call_count": sum(s["tool_call_count"] for s in scenarios),
                "tool_call_counts": run_tool_counts,
            },
            "scenarios": scenarios,
        }
