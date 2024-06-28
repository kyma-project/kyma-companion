from fastapi import FastAPI

from utils.logging import get_logger
from utils.models import get_model

logger = get_logger(__name__)

app = FastAPI()


def init_chat() -> dict:
    """ Initialize the chat """
    logger.info("Initializing chat...")
    return {"message": "Chat is initialized!"}


def chatting() -> dict:
    """ Chat with the Kyma companion """
    logger.info("Processing request...")

    llm = get_model("gpt-4o")
    logger.info(f"LLM model {llm} is created.")

    return {"message": "Hello!"}


@app.get("/chat/init")
async def init() -> dict:
    """ Endpoint to initialize the chat with the Kyma companion """
    return init_chat()


@app.get("/chat")
async def chat() -> dict:
    """ Endpoint to chat with the Kyma companion """
    return chatting()
