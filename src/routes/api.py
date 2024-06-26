from fastapi import FastAPI, HTTPException
from utils.logging import get_logger

logger = get_logger(__name__)

app = FastAPI()


@app.get("/chat")
async def chat():
    logger.info("Processing request...")
    return {"message": "Hello World!"}
