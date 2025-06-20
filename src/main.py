from http import HTTPStatus
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from starlette.responses import JSONResponse

from agents.common.constants import ERROR_RATE_LIMIT_CODE
from routers.conversations import router as conversations_router
from routers.probes import router as probes_router
from services.metrics import CustomMetrics
from utils.logging import get_logger

logger = get_logger(__name__)
app = FastAPI(
    title="Kyma-Companion.",
)


@app.middleware("http")
async def monitor_http_requests(req: Request, call_next: Any) -> Any:
    """A middleware to monitor HTTP requests."""
    return await CustomMetrics().monitor_http_requests(req, call_next)


@app.middleware("http")
async def exception_handler_middleware(req: Request, call_next: Any) -> Any:
    """Middleware to handle HTTP and generic exceptions."""
    try:
        return await call_next(req)

    except HTTPException as http_exc:
        logger.error(f"HTTPException {http_exc.status_code}: {http_exc}")
        return await handle_http_exception(http_exc)

    except Exception:
        logger.error("Unhandled exception occurred", exc_info=True)
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal Server Error",
                "message": "An unexpected error occurred. Please try again later.",
            },
        )


async def handle_http_exception(exc: HTTPException) -> JSONResponse:
    """Handles known HTTPException status codes."""
    status = exc.status_code
    default_response = {
        "error": "Request Error",
        "message": "An error occurred, Please try again later.",
    }

    response_map = {
        HTTPStatus.UNAUTHORIZED: {
            "error": "Unauthorized",
            "message": "Authentication failed",
        },
        HTTPStatus.FORBIDDEN: {
            "error": "Unauthorized",
            "message": "Authentication failed",
        },
        HTTPStatus.NOT_FOUND: {
            "error": "Not Found",
            "message": "Requested resource not found",
        },
        HTTPStatus.BAD_REQUEST: {
            "error": "Bad Request",
            "message": "Invalid request format or parameters",
        },
        HTTPStatus.UNPROCESSABLE_ENTITY: {
            "error": "Validation Error",
            "message": "Request validation failed",
        },
        HTTPStatus.METHOD_NOT_ALLOWED: {
            "error": "Method Not Allowed",
            "message": "HTTP method not supported for this endpoint",
        },
        HTTPStatus.INTERNAL_SERVER_ERROR: {
            "error": "Internal Server Error",
            "message": "Something went wrong.",
        },
        HTTPStatus.REQUEST_TIMEOUT: {
            "error": "Request Timeout",
            "message": "Request took too long to process",
        },
    }

    if status == ERROR_RATE_LIMIT_CODE:
        return JSONResponse(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            content=exc.detail,
            headers=exc.headers,
        )

    return JSONResponse(
        status_code=status,
        content=response_map.get(status, default_response),
    )


app.include_router(conversations_router)
app.include_router(probes_router)


@app.get("/")
async def root() -> dict:
    """The root endpoint of the API."""
    return {"message": "Kyma Companion!"}


@app.get("/metrics")
async def metrics() -> Response:
    """The endpoint to expose the metrics."""
    return CustomMetrics().generate_http_response()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
