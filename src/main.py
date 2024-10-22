from fastapi import FastAPI

from routers import conversations

app = FastAPI(
    title="Kyma Companion",
)
app.include_router(conversations.router)


# TODO: This comment is only here to trigger the build job, so the eval test can run.
# Before merging this PR remove this comment.
@app.get("/")
async def root() -> dict:
    """The root endpoint of the API."""
    return {"message": "Hello from Kyma Companion!"}


@app.get("/readyz")
async def readyz() -> dict:
    """Endpoint for the Readiness Probe."""
    return {"ready": "true"}


@app.get("/healthz")
async def healthz() -> dict:
    """Endpoint for the Health Probe."""
    return {"healthy": "true"}
