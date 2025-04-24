from fastapi import APIRouter

router = APIRouter(
    tags=["probes"],
)


@router.get("/readyz")
async def readyz() -> dict:
    """The endpoint for the Readiness Probe."""
    return {"ready": "true"}


@router.get("/healthz")
async def healthz() -> dict:
    """The endpoint for the Health Probe."""
    return {"healthy": "true"}
