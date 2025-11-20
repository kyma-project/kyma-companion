from http import HTTPStatus
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from starlette.responses import JSONResponse

from agents.common.constants import ERROR_RATE_LIMIT_CODE
from routers.conversations import router as conversations_router
from routers.probes import router as probes_router
from routers.rag_api import router as rag_router
from services.metrics import CustomMetrics
from utils.logging import get_logger

logger = get_logger(__name__)
app = FastAPI(
    title="Joule",
)


@app.middleware("http")
async def monitor_http_requests(req: Request, call_next: Any) -> Any:
    """A middleware to monitor HTTP requests."""
    return await CustomMetrics().monitor_http_requests(req, call_next)


@app.exception_handler(HTTPException)
@app.exception_handler(RequestValidationError)
@app.exception_handler(ResponseValidationError)
async def custom_http_exception_handler(
    request: Request,
    exc: HTTPException | RequestValidationError | ResponseValidationError,
) -> JSONResponse:
    """Exception Handler for HTTPException."""
    logger.error("HTTPException", exc_info=(type(exc), exc, exc.__traceback__))
    return handle_http_exception(exc)


@app.exception_handler(Exception)
async def custom_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Exception Handler all exceptions other than HTTPException."""
    logger.error("Unhandled exception occurred", exc_info=(type(exc), exc, exc.__traceback__))
    return JSONResponse(
        status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
        content={
            "error": "Internal Server Error",
            "message": "An unexpected error occurred. Please try again later.",
        },
    )


def handle_http_exception(
    exc: HTTPException | RequestValidationError | ResponseValidationError,
) -> JSONResponse:
    """Handles known HTTPException status codes."""
    exc_detail: Any = []
    if isinstance(exc, HTTPException):
        status = exc.status_code
    elif isinstance(exc, RequestValidationError | ResponseValidationError):
        status = HTTPStatus.UNPROCESSABLE_ENTITY
        exc_detail = exc.errors()
    else:
        status = HTTPStatus.INTERNAL_SERVER_ERROR

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
            "detail": exc_detail,
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
            status_code=ERROR_RATE_LIMIT_CODE,
            content=exc.detail,
            headers=exc.headers,
        )

    return JSONResponse(
        status_code=status,
        content=response_map.get(HTTPStatus(status), default_response),
    )


app.include_router(conversations_router)
app.include_router(probes_router)
app.include_router(rag_router)


@app.get("/")
async def root() -> dict:
    """The root endpoint of the API."""
    return {"message": "Joule!"}


@app.get("/metrics")
async def metrics() -> Response:
    """The endpoint to expose the metrics."""
    return CustomMetrics().generate_http_response()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
