import uvicorn

from src.routes.api import app  # noqa: F401 - uvicorn needs to import the app

if __name__ == "__main__":
    config = uvicorn.Config(
        app="main:app",
        port=8000,
        log_level="info",
        use_colors=True,
    )
    server = uvicorn.Server(config)
    server.run()
