from fastapi import FastAPI
from starlette.responses import StreamingResponse

from services.chat import init_chat, process_chat_request

app = FastAPI()


@app.get("/chat/init")
async def init() -> dict:
    """ Endpoint to initialize the chat with the Kyma companion """
    return await init_chat()


@app.get("/chat")
async def chat() -> StreamingResponse:
    """ Endpoint to chat with the Kyma companion """
    return StreamingResponse(process_chat_request(), media_type='text/event-stream')
