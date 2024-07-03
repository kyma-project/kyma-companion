from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from src.utils.logging import get_logger
from src.services.chat import init_chat, process_chat_request

logger = get_logger(__name__)

app = FastAPI()


@app.get("/chat/init")
async def init() -> dict:
    """ Endpoint to initialize the chat with the Kyma companion """
    return await init_chat()


@app.get("/chat")
async def chat() -> dict:
    """ Endpoint to chat with the Kyma companion """
    return StreamingResponse(process_chat_request(), media_type='text/event-stream')
