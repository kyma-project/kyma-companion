from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI  # noqa E402
from routers import chat  # noqa E402

app = FastAPI()
app.include_router(chat.router)


@app.get("/")
async def root() -> dict:  # noqa E302
    return {"message": "Hello from Kyma Companion!"}


@app.get("/readyz")
async def readyz() -> dict:  # noqa E302
    return {"ready": "true"}


@app.get("/healthz")
async def healthz() -> dict:  # noqa E302
    return {"healthy": "true"}
