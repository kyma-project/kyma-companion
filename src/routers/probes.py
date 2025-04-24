from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE

from routers.common import LivenessModel, ReadynessModel
from services.probes import Readyness
from utils.hana import create_hana_connection
from utils.redis import create_redis_connection
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

router = APIRouter(
    tags=["probes"],
)
readyness_probe = Readyness(
    hana_connection=create_hana_connection(
        url=str(DATABASE_URL),
        port=DATABASE_PORT,
        user=str(DATABASE_USER),
        password=str(DATABASE_PASSWORD),
    ),
    redis_connection=create_redis_connection(
        host=str(REDIS_HOST),
        port=REDIS_PORT,
        db=REDIS_DB_NUMBER,
        password=str(REDIS_PASSWORD),
    ),
)


@router.get("/readyz")
async def readyz() -> JSONResponse:
    """The endpoint for the Readiness Probe."""
    response = readyness_probe.get_dto()
    status = HTTP_200_OK if all_ready(response) else HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(content=jsonable_encoder(response), status_code=status)


@router.get("/healthz")
async def healthz() -> JSONResponse:
    """The endpoint for the Health Probe."""
    response = LivenessModel(
        is_redis_ready=True,
        is_hana_ready=True,
        llms={
            "llm1": True,
            "llm2": True,
        },
    )

    status = HTTP_503_SERVICE_UNAVAILABLE
    if all_ready(response):
        status = HTTP_200_OK

    return JSONResponse(content=jsonable_encoder(response), status_code=status)


def all_ready(response: ReadynessModel | LivenessModel) -> bool:
    """
    Check if all components are ready.
    """
    if isinstance(response, ReadynessModel):
        return response.is_redis_ready and response.is_hana_ready and all(response.llms.values())
    if isinstance(response, LivenessModel):
        return response.is_redis_ready and response.is_hana_ready and all(response.llms.values())
