from typing import Protocol

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from hdbcli import dbapi
from redis.typing import ResponseT
from starlette.responses import JSONResponse
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE

from routers.common import LivenessModel, ReadinessModel
from services.hana import get_hana_connection
from services.probes import get_llm_readiness_probe
from services.redis import get_redis_connection
from utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(
    tags=["probes"],
)


class IHanaConnection(Protocol):
    """Protocol for the Hana database connection."""

    def isconnected(self) -> bool:
        """Verifies if a connection to a Hana database is ready."""
        ...


class IRedisConnection(Protocol):
    """
    Protocol to ensure the Redis connection has a `ping` method.
    """

    def ping(self, **kwargs) -> ResponseT:  # noqa
        """Ping the Redis server."""
        ...


class ILLMReadinessProbe(Protocol):
    """
    Protocol for probing the readiness of LLMs (Large Language Models).
    """

    def get_llms_states(self) -> dict[str, bool]:
        """
        Retrieve the readiness states of all LLMs.

        Returns:
            A dictionary where the keys are LLM names and the values are booleans
            indicating whether each LLM is ready.
        """
        ...

    def has_models(self) -> bool:
        """
        Check if there are any models available.

        Returns:
            bool: True if models are available, False otherwise.
        """
        ...


@router.get("/readyz")
async def readyz(
    hana_conn: IHanaConnection = Depends(get_hana_connection),  # noqa: B008
    redis_conn: IRedisConnection = Depends(get_redis_connection),  # noqa: B008
    llm_probe: ILLMReadinessProbe = Depends(get_llm_readiness_probe),  # noqa: B008
) -> JSONResponse:
    """The endpoint for the Readiness Probe."""

    response = ReadinessModel(
        is_hana_ready=is_hana_ready(hana_conn),
        is_redis_ready=is_redis_ready(redis_conn),
        llms=llm_probe.get_llms_states(),
    )

    return JSONResponse(
        content=jsonable_encoder(response),
        status_code=(
            HTTP_200_OK if all_ready(response) else HTTP_503_SERVICE_UNAVAILABLE
        ),
    )


@router.get("/healthz")
async def healthz(
    hana_conn: IHanaConnection = Depends(get_hana_connection),  # noqa: B008
    redis_conn: IRedisConnection = Depends(get_redis_connection),  # noqa: B008
    llm_probe: ILLMReadinessProbe = Depends(get_llm_readiness_probe),  # noqa: B008
) -> JSONResponse:
    """The endpoint for the Health Probe."""
    response = LivenessModel(
        is_hana_initialized=bool(hana_conn),
        is_redis_initialized=bool(redis_conn),
        are_models_initialized=llm_probe.has_models(),
    )
    status = HTTP_503_SERVICE_UNAVAILABLE
    if all_ready(response):
        status = HTTP_200_OK

    return JSONResponse(content=jsonable_encoder(response), status_code=status)


def all_ready(response: ReadinessModel | LivenessModel) -> bool:
    """
    Check if all components are ready.
    """
    if isinstance(response, ReadinessModel):
        return (
            response.is_redis_ready
            and response.is_hana_ready
            and all(response.llms.values())
        )
    if isinstance(response, LivenessModel):
        return (
            response.is_redis_initialized
            and response.is_hana_initialized
            and response.are_models_initialized
        )


def is_hana_ready(connection: IHanaConnection) -> bool:
    """
    Check if the HANA database is ready.

    Returns:
        bool: True if HANA is ready, False otherwise.
    """
    if not connection:
        logger.warning("HANA DB connection is not initialized.")
        return False

    try:
        if connection.isconnected():
            logger.info("HANA DB connection is ready.")
            return True
        logger.info("HANA DB connection is not ready.")
    except dbapi.Error as e:
        logger.error(f"Error while connecting to HANA DB: {e}")

    return False


def is_redis_ready(connection: IRedisConnection) -> bool:
    """
    Check if the Redis service is ready.

    Returns:
        bool: True if Redis is ready, False otherwise.
    """
    if not connection:
        logger.error("Redis connection is not initialized.")
        return False

    try:
        if connection.ping():
            logger.info("Redis connection is ready.")
            return True
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
    return False
