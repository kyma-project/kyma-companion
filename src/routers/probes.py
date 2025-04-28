import asyncio
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

    async def get_llms_states(self) -> dict[str, bool]:
        """
        Retrieve the readiness states of all LLMs.

        Returns:
            A dictionary where the keys are LLM names and the values are booleans
            indicating whether each LLM is ready.
        """
        ...

    async def has_models(self) -> bool:
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
    logger.info("Ready probe called.")

    # Create tasks.
    hana_task = is_hana_ready(hana_conn)
    redis_task = is_redis_ready(redis_conn)
    llms_task = llm_probe.get_llms_states()

    # Run tasks.
    hana_result, redis_result, llms_result = await asyncio.gather(
        hana_task, redis_task, llms_task
    )

    # Collect results.
    response = ReadinessModel(
        is_hana_ready=hana_result,
        is_redis_ready=redis_result,
        llms=llms_result,
    )

    # Set the status code.
    status = HTTP_503_SERVICE_UNAVAILABLE
    if all_ready(response):
        status = HTTP_200_OK

    logger.info(f"Health probe returning status: {status}")
    logger.info(f"Health probe returning body: {response}")

    return JSONResponse(
        content=jsonable_encoder(response),
        status_code=(status),
    )


@router.get("/healthz")
async def healthz(
    hana_conn: IHanaConnection = Depends(get_hana_connection),  # noqa: B008
    redis_conn: IRedisConnection = Depends(get_redis_connection),  # noqa: B008
    llm_probe: ILLMReadinessProbe = Depends(get_llm_readiness_probe),  # noqa: B008
) -> JSONResponse:
    """The endpoint for the Health Probe."""
    logger.info("Health probe called.")
    response = LivenessModel(
        is_hana_initialized=bool(hana_conn),
        is_redis_initialized=bool(redis_conn),
        are_models_initialized=await llm_probe.has_models(),
    )
    status = HTTP_503_SERVICE_UNAVAILABLE
    if all_ready(response):
        status = HTTP_200_OK
    logger.info(f"Health probe returning status: {status}")
    logger.info(f"Health probe returning body: {response}")
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


async def is_hana_ready(connection: IHanaConnection) -> bool:
    """
    Check if the HANA database is ready.

    Returns:
        bool: True if HANA is ready, False otherwise.
    """
    if not connection:
        logger.warning("HANA DB connection is not initialized.")
        return False

    try:
        is_connected = await asyncio.to_thread(connection.isconnected)
        if is_connected:
            logger.info("HANA DB connection is ready.")
            return True
        logger.info("HANA DB connection is not ready.")
    except dbapi.Error as e:
        logger.error(f"Error while connecting to HANA DB: {e}")

    return False


async def is_redis_ready(connection: IRedisConnection) -> bool:
    """
    Check if the Redis service is ready.

    Returns:
        bool: True if Redis is ready, False otherwise.
    """
    if not connection:
        logger.error("Redis connection is not initialized.")
        return False

    try:
        is_ready = await asyncio.to_thread(connection.ping)
        if is_ready:
            logger.info("Redis connection is ready.")
            return True
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
    return False
