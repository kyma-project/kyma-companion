import uvicorn
from routes.api import app

if __name__ == "__main__":
    config = uvicorn.Config(
        app="main:app",
        port=8000,
        log_level="info"
    )
    server = uvicorn.Server(config)
    server.run()
