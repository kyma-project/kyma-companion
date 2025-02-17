from fastapi import FastAPI

from routers import conversations

app = FastAPI(
    title="Kyma Companion",
)
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
