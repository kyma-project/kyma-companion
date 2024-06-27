from fastapi import FastAPI

from utils.logging import get_logger

logger = get_logger(__name__)

app = FastAPI()


@app.get("/chat")
async def chat() -> dict:
    """ Endpoint to chat with the Kyma companion """
    logger.info("Processing request...")
    return {"message": "Hello World!"}
