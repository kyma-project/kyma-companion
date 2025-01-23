from pydantic import BaseModel, Field


class Usage(BaseModel):
    """Represents the usage metrics for an LLM model."""

    model: str | None
    input_usage: int = Field(alias="inputUsage")
    output_usage: int = Field(alias="outputUsage")
    total_usage: int = Field(alias="totalUsage")
    total_cost: float = Field(alias="totalCost")
    count_observations: int = Field(alias="countObservations")
    count_traces: int = Field(alias="countTraces")


class DailyMetrics(BaseModel):
    """Represents daily metrics for traces, observations, and costs."""

    date: str
    count_traces: int = Field(alias="countTraces")
    count_observations: int = Field(alias="countObservations")
    total_cost: float = Field(alias="totalCost")
    usage: list[Usage]


class Meta(BaseModel):
    """Represents metadata for pagination and item counts."""

    page: int
    limit: int
    total_items: int = Field(alias="totalItems")
    total_pages: int = Field(alias="totalPages")


class MetricsResponse(BaseModel):
    """Represents a response containing daily metrics and metadata."""

    data: list[DailyMetrics]
    meta: Meta
