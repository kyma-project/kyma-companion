from fastapi import FastAPI, HTTPException

app = FastAPI()


@app.get("/chat")
async def chat():
    return {"message": "Hello World!"}
