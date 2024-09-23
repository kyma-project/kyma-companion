from fastapi import FastAPI

from routers import conversations

app = FastAPI(
    title="Kyma Companion",
)
app.include_router(conversations.router)


@app.get("/")
async def root() -> dict:  # noqa E302
    return {"message": "Hello from Kyma Companion!"}


@app.get("/readyz")
async def readyz() -> dict:  # noqa E302
    return {"ready": "true"}


@app.get("/healthz")
async def healthz() -> dict:  # noqa E302
    return {"healthy": "true"}
