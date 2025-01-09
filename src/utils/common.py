from pydantic import BaseModel


class Usage(BaseModel):
    """Represents the usage metrics for an LLM model."""

    model: str | None
    input_usage: int
    output_usage: int
    total_usage: int
    total_cost: float
    count_observations: int
    count_traces: int


class DailyMetrics(BaseModel):
    """Represents daily metrics for traces, observations, and costs."""

    date: str
    count_traces: int
    count_observations: int
    total_cost: float
    usage: list[Usage]


class Meta(BaseModel):
    """Represents metadata for pagination and item counts."""

    page: int
    limit: int
    total_items: int
    total_pages: int


class MetricsResponse(BaseModel):
    """Represents a response containing daily metrics and metadata."""

    data: list[DailyMetrics]
    meta: Meta
