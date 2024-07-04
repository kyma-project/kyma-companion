from fastapi import FastAPI

from routers import chat

app = FastAPI()
app.include_router(chat.router)


@app.get("/")
async def root() -> dict:  # noqa E302
    return {"message": "Hello from Kyma Companion!"}
