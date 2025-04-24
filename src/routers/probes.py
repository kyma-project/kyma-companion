from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from starlette.responses import JSONResponse
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE

from routers.common import LivenessModel, ReadynessModel
from services.probes import Readyness

router = APIRouter(
    tags=["probes"],
)
readyness_probe = Readyness()


@router.get("/readyz")
async def readyz() -> JSONResponse:
    """The endpoint for the Readiness Probe."""
    response = readyness_probe.get_dto()
    status = HTTP_503_SERVICE_UNAVAILABLE
    if all_ready(response):
        status = HTTP_200_OK

    return JSONResponse(content=jsonable_encoder(response), status_code=status)


@router.get("/healthz")
async def healthz() -> JSONResponse:
    """The endpoint for the Health Probe."""
    response = LivenessModel(
        is_redis_ready=True,
        is_hana_ready=True,
        llms={
            "llm1": False,
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
        return (
            response.is_redis_ready
            and response.is_hana_ready
            and all(response.llms.values())
        )
    if isinstance(response, LivenessModel):
        return (
            response.is_redis_ready
            and response.is_hana_ready
            and all(response.llms.values())
        )
