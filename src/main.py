import logging
import sys
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from starlette.responses import JSONResponse

from agents.common.constants import ERROR_RATE_LIMIT_CODE
from routers.conversations import router as conversations_router
from routers.k8s_tools_api import router as k8s_tools_router
from routers.kyma_tools_api import router as kyma_tools_router
from routers.probes import router as probes_router
from services.metrics import CustomMetrics
from utils.exceptions import K8sClientError
from utils.logging import get_logger, reconfigure_logging
from utils.settings import HOST, PORT

logger = get_logger(__name__)
access_logger = get_logger("access")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Lifespan event handler to reconfigure logging after uvicorn starts."""
    # Only reconfigure logging when NOT running tests
    # During tests, logging is already configured by utils.logging on import
    if "pytest" not in sys.modules:
        # Reconfigure logging after uvicorn has applied its config
        reconfigure_logging()
    yield


# Probe endpoints for efficient path checking
PROBE_PATHS = frozenset(["/healthz", "/readyz"])

app = FastAPI(
    title="Joule",
    lifespan=lifespan,
)


@app.middleware("http")
async def logging_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Log HTTP requests with appropriate log levels and timing.

    - Probe endpoints (/healthz, /readyz) with 200 → DEBUG
    - Probe endpoints with non-200 → WARNING
    - All other requests → INFO
    """
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000

    # Determine log level based on path and status
    is_probe = request.url.path in PROBE_PATHS
    if is_probe:  # noqa: SIM108
        level = logging.DEBUG if response.status_code == HTTPStatus.OK else logging.WARNING
    else:
        level = logging.INFO

    # Log with structured data (works well with JSON formatter)
    client_host = request.client.host if request.client else "unknown"
    access_logger.log(
        level,
        f'{client_host} - "{request.method} {request.url.path}" {response.status_code}',
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "client": client_host,
        },
    )

    return response


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
    """An Exception Handler for HTTPException."""
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
        # Preserve detailed error messages from K8sClientError
        if isinstance(exc.__cause__, K8sClientError):
            return JSONResponse(
                status_code=status,
                content={"detail": exc.detail},
            )
    elif isinstance(exc, RequestValidationError | ResponseValidationError):
        status = HTTPStatus.UNPROCESSABLE_ENTITY
        # Use FastAPI's jsonable_encoder to handle bytes and other non-JSON types
        # This follows the same approach as FastAPI's built-in exception handler
        exc_detail = jsonable_encoder(exc.errors())
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
app.include_router(k8s_tools_router)
app.include_router(kyma_tools_router)
app.include_router(probes_router)


@app.get("/")
async def root() -> dict:
    """The root endpoint of the API."""
    return {"message": "Joule!"}


@app.get("/metrics")
async def metrics() -> Response:
    """The endpoint to expose the metrics."""
    return CustomMetrics().generate_http_response()


if __name__ == "__main__":
    # Logging is already configured in utils.logging
    # Disable uvicorn's log config to use our custom configuration
    # Host and port are loaded from settings (configurable via environment variables)
    uvicorn.run(app, host=HOST, port=PORT, log_config=None)
