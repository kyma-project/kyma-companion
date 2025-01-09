from pydantic import BaseModel
from typing import List, Optional

# Define the Usage model
class Usage(BaseModel):
    model: Optional[str]
    inputUsage: int
    outputUsage: int
    totalUsage: int
    totalCost: float
    countObservations: int
    countTraces: int

# Define the DailyMetrics model
class DailyMetrics(BaseModel):
    date: str
    countTraces: int
    countObservations: int
    totalCost: float
    usage: List[Usage]

# Define the Meta model
class Meta(BaseModel):
    page: int
    limit: int
    totalItems: int
    totalPages: int

# Define the overall MetricsResponse model
class MetricsResponse(BaseModel):
    data: List[DailyMetrics]
    meta: Meta