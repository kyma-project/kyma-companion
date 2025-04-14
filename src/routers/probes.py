from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from redis.asyncio import Redis
from starlette.responses import JSONResponse
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE

from routers.common import LivenessModel, ReadynessModel
from services.probes import Probe
from utils.config import get_config
from utils.hana import create_hana_connection
from utils.logging import get_logger
from utils.models.factory import ModelFactory
from utils.settings import (
    DATABASE_PASSWORD,
    DATABASE_PORT,
    DATABASE_URL,
    DATABASE_USER,
    REDIS_DB_NUMBER,
    REDIS_HOST,
    REDIS_PASSWORD,
    REDIS_PORT,
)

logger = get_logger(__name__)


router = APIRouter(
    tags=["conversations"],
)

hana_connection = create_hana_connection(
    url=str(DATABASE_URL),
    port=DATABASE_PORT,
    user=str(DATABASE_USER),
    password=str(DATABASE_PASSWORD),
)

redis_connection = Redis(
    host=str(REDIS_HOST),
    port=REDIS_PORT,
    db=REDIS_DB_NUMBER,
    password=str(REDIS_PASSWORD),
)

models = ModelFactory(config=get_config()).create_models()


@router.get("/readyz", response_model=ReadynessModel)
async def get_readyz() -> JSONResponse:
    """Endpoint for the Kubernetes readyz probe."""
    probe = Probe(hana_connection, redis_connection, models)

    response = LivenessModel(
        is_hana_ready=False,
        is_redis_ready=False,
        is_ai_core_ready=True,
    )
    response.is_hana_ready = probe.is_hana_connection_ready()
    response.is_redis_ready = await probe.is_redis_connection_ready()
    response.is_ai_core_ready = probe.are_model_connections_okay()

    status = HTTP_503_SERVICE_UNAVAILABLE
    if response.is_hana_ready and response.is_redis_ready and response.is_ai_core_ready:
        status = HTTP_200_OK

    return JSONResponse(content=jsonable_encoder(response), status_code=status)


@router.get("/healthz", response_model=LivenessModel)
async def get_healthz() -> JSONResponse:
    """Endpoint for the Kubernetes healthz probe."""
    response = LivenessModel(
        is_hana_ready=False,
        is_redis_ready=False,
        is_ai_core_ready=True,
    )
    probe = Probe(
        hana_connection,
        redis_connection,
        models,
    )

    response.is_hana_ready = probe.is_hana_connection_ready()
    response.is_redis_ready = await probe.is_redis_connection_ready()
    response.is_ai_core_ready = probe.are_model_connections_okay()

    status = HTTP_503_SERVICE_UNAVAILABLE
    if response.is_hana_ready and response.is_redis_ready and response.is_ai_core_ready:
        status = HTTP_200_OK

    return JSONResponse(content=jsonable_encoder(response), status_code=status)
