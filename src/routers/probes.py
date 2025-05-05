from typing import Protocol

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from redis.typing import ResponseT
from starlette.responses import JSONResponse
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE

from routers.common import HealthModel, ReadinessModel
from services.hana import get_hana
from services.probes import (
    get_llm_probe,
    get_usage_tracke_probe,
)
from services.redis import get_redis
from utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(
    tags=["probes"],
)


class IUsageTrackerProbe(Protocol):
    """Protocol defining the interface for UsageTrackerProbe."""

    def reset_failure_count(self) -> None:
        """Sets the failure count back to 0."""
        ...

    def increase_failure_count(self) -> None:
        """Increases the failure count by 1."""
        ...

    def is_healthy(self) -> bool:
        """Checks if the failure count is equal or greater than the threshold."""
        ...


class IHanaConnection(Protocol):
    """Protocol for the Hana database connection."""

    def isconnected(self) -> bool:
        """Verifies if a connection to a Hana database is ready."""
        ...


class IHana(Protocol):
    """
    Protocol for defining an IHana service.

    Attributes:
        connection (IHanaConnection): Represents the connection to the Hana database.
    """

    connection: IHanaConnection

    def is_connection_operational(self) -> bool:
        """
        Check if the Hana service is operational.
        """
        ...

    def has_connection(self) -> bool:
        """Check if a connection exists."""
        ...


class IRedisConnection(Protocol):
    """
    Protocol to ensure the Redis connection has a `ping` method.
    """

    def ping(self, **kwargs) -> ResponseT:  # noqa
        """Ping the Redis server."""
        ...


class IRedis(Protocol):
    """
    Protocol for defining an IRedis service.

    Attributes:
        connection (IRedisConnection): Represents the connection to the Redis database.
    """

    connection: IRedisConnection

    async def is_connection_operational(self) -> bool:
        """
        Check if the Redis service is operational.
        """
        ...

    def has_connection(self) -> bool:
        """Check if a connection exists."""
        ...


class ILLMProbe(Protocol):
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


@router.get("/healthz")
async def healthz(
    hana: IHana = Depends(get_hana),  # noqa: B008
    redis: IRedis = Depends(get_redis),  # noqa: B008
    usage_tracker_probe: IUsageTrackerProbe = Depends(  # noqa: B008
        get_usage_tracke_probe
    ),
    llm_probe: ILLMProbe = Depends(get_llm_probe),  # noqa: B008
) -> JSONResponse:
    """The endpoint for the Health Probe."""

    logger.info("Ready probe called.")
    response = HealthModel(
        is_hana_healthy=hana.is_connection_operational(),
        is_redis_healthy=await redis.is_connection_operational(),
        is_usage_tracker_healthy=usage_tracker_probe.is_healthy(),
        llms=llm_probe.get_llms_states(),
    )

    status = HTTP_503_SERVICE_UNAVAILABLE
    if all_ready(response):
        status = HTTP_200_OK
    logger.info(f"Health probe returning status: {status}")
    logger.info(f"Health probe returning body: {response}")

    return JSONResponse(
        content=jsonable_encoder(response),
        status_code=(status),
    )


@router.get("/readyz")
async def readyz(
    hana: IHana = Depends(get_hana),  # noqa: B008
    redis: IRedis = Depends(get_redis),  # noqa: B008
    llm_probe: ILLMProbe = Depends(get_llm_probe),  # noqa: B008
) -> JSONResponse:
    """The endpoint for the Ready Probe."""

    logger.info("Health probe called.")
    response = ReadinessModel(
        is_hana_initialized=hana.has_connection(),
        is_redis_initialized=redis.has_connection(),
        are_models_initialized=llm_probe.has_models(),
    )
    status = HTTP_503_SERVICE_UNAVAILABLE
    if all_ready(response):
        status = HTTP_200_OK
    logger.info(f"Health probe returning status: {status}")
    logger.info(f"Health probe returning body: {response}")
    return JSONResponse(content=jsonable_encoder(response), status_code=status)


def all_ready(response: HealthModel | ReadinessModel) -> bool:
    """
    Check if all components are ready.
    """
    if isinstance(response, HealthModel):
        return (
            response.is_redis_healthy
            and response.is_hana_healthy
            and response.is_usage_tracker_healthy
            and bool(response.llms)
            and all(response.llms.values())
        )
    if isinstance(response, ReadinessModel):
        return (
            response.is_redis_initialized
            and response.is_hana_initialized
            and response.are_models_initialized
        )
