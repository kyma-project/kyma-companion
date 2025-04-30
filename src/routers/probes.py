from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE

from routers.common import HealthModel, ReadinessModel
from services.hana import get_hana_connection
from services.metrics import CustomMetrics, get_custom_metrics
from services.probes import (
    IHana,
    ILLMReadinessProbe,
    IRedis,
    get_llm_readiness_probe,
    is_hana_ready,
    is_redis_ready,
    is_usage_tracker_ready,
)
from services.redis import get_redis_connection
from utils.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(
    tags=["probes"],
)


@router.get("/healthz")
async def healthz(
    hana: IHana = Depends(get_hana_connection),  # noqa: B008
    redis: IRedis = Depends(get_redis_connection),  # noqa: B008
    metrics: CustomMetrics = Depends(get_custom_metrics),  # noqa: B008
    llm_probe: ILLMReadinessProbe = Depends(get_llm_readiness_probe),  # noqa: B008
) -> JSONResponse:
    """The endpoint for the Health Probe."""

    logger.info("Ready probe called.")
    response = HealthModel(
        is_hana_ready=is_hana_ready(hana.connection),
        is_redis_ready=is_redis_ready(redis.connection),
        is_usage_tracker_ready=is_usage_tracker_ready(metrics),
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
    hana: IHana = Depends(get_hana_connection),  # noqa: B008
    redis_conn: IRedis = Depends(get_redis_connection),  # noqa: B008
    llm_probe: ILLMReadinessProbe = Depends(get_llm_readiness_probe),  # noqa: B008
) -> JSONResponse:
    """The endpoint for the Ready Probe."""

    logger.info("Health probe called.")
    response = ReadinessModel(
        is_hana_initialized=bool(hana.connection),
        is_redis_initialized=bool(redis_conn.connection),
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
            response.is_redis_ready
            and response.is_hana_ready
            and response.is_usage_tracker_ready
            and bool(response.llms)
            and all(response.llms.values())
        )
    if isinstance(response, ReadinessModel):
        return (
            response.is_redis_initialized
            and response.is_hana_initialized
            and response.are_models_initialized
        )
