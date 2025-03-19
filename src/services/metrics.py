import time
from enum import Enum
from http import HTTPStatus
from typing import Any

from fastapi import Request
from prometheus_client import Counter, Histogram
from starlette.routing import Match

from utils.singleton_meta import SingletonMeta

METRICS_KEY_PREFIX = "kyma_companion"
REQUEST_LATENCY_METRIC_KEY = f"{METRICS_KEY_PREFIX}_http_request_duration_seconds"
USAGE_TRACKER_PUBLISH_FAILURE_METRIC_KEY = (
    f"{METRICS_KEY_PREFIX}_usage_tracker_publish_failure_count"
)
LANGGRAPH_ERROR_METRIC_KEY = f"{METRICS_KEY_PREFIX}_langgraph_error_count"


class LangGraphErrorType(Enum):
    """An Enum to represent the LangGraph error types."""

    LLM_ERROR = "llm_error"
    TOOL_ERROR = "tool_error"
    RETRIEVER_ERROR = "retriever_error"
    CHAIN_ERROR = "chain_error"


class CustomMetrics(metaclass=SingletonMeta):
    """A class to handle custom metrics."""

    def __init__(self):
        self.request_latency = Histogram(
            REQUEST_LATENCY_METRIC_KEY,
            "HTTP Request Duration",
            ["method", "status", "path"],
        )
        self.usage_tracker_publish_failure_count = Counter(
            USAGE_TRACKER_PUBLISH_FAILURE_METRIC_KEY,
            "Token Usage Tracker Publish Count",
        )
        self.langgraph_error_count = Counter(
            LANGGRAPH_ERROR_METRIC_KEY, "LangGraph Error Count", ["error_type"]
        )

    async def record_token_usage_tracker_publish_failure(self) -> None:
        """Record the token usage tracker publish failure count."""
        self.usage_tracker_publish_failure_count.inc()

    async def record_langgraph_error(self, error_type: LangGraphErrorType) -> None:
        """Record the LangGraph error count."""
        self.langgraph_error_count.labels(error_type=error_type.value).inc()

    async def monitor_http_requests(self, req: Request, call_next: Any) -> Any:
        """A middleware to monitor HTTP requests."""
        method = req.method
        # get the path of the request (without path parameters injected).
        path = ""
        for route in req.app.routes:
            match, _ = route.matches(req.scope)
            if match == Match.FULL:
                path = route.path
                break

        # wait for the response.
        start_time = time.perf_counter()
        try:
            response = await call_next(req)
        except Exception as e:
            # record metric and then throw exception.
            req_duration = time.perf_counter() - start_time
            self.request_latency.labels(
                method=method, status=HTTPStatus.INTERNAL_SERVER_ERROR, path=path
            ).observe(req_duration)
            raise e

        # record metric.
        req_duration = time.perf_counter() - start_time
        self.request_latency.labels(
            method=method, status=response.status_code, path=path
        ).observe(req_duration)

        # continue request handling.
        return response
