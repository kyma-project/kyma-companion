from typing import Any

import uvicorn
from fastapi import FastAPI, Request, Response

from routers import conversations
from services.metrics import CustomMetrics

app = FastAPI(
    title="Kyma Companion",
)


@app.middleware("http")
async def monitor_http_requests(req: Request, call_next: Any) -> Any:
    """A middleware to monitor HTTP requests."""
    return await CustomMetrics().monitor_http_requests(req, call_next)


app.include_router(conversations.router)


@app.get("/")
async def root() -> dict:
    """The root endpoint of the API."""
    return {"message": "Kyma Companion!"}


@app.get("/readyz")
async def readyz() -> dict:
    """The endpoint for the Readiness Probe."""
    return {"ready": "true"}


@app.get("/healthz")
async def healthz() -> dict:
    """The endpoint for the Health Probe."""
    return {"healthy": "true"}


@app.get("/metrics")
async def metrics() -> Response:
    """The endpoint to expose the metrics."""
    return CustomMetrics().generate_http_response()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
