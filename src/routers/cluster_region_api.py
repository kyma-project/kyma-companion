"""
Cluster Region REST API Router.

Exposes cluster region information for a given shoot-id by reading
Runtime CRs from the KCP cluster. No k8s auth headers are required
from the caller — the pod's in-cluster service account is used.
"""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path

from routers.common import API_PREFIX, ClusterRegionResponse
from services.cluster_region import get_cluster_region
from utils.logging import get_logger

logger = get_logger(__name__)


router = APIRouter(
    prefix=f"{API_PREFIX}/tools",
    tags=["cluster-region"],
)


@router.get("/cluster-region/{shoot_id}", response_model=ClusterRegionResponse)
async def cluster_region(
    shoot_id: Annotated[
        str,
        Path(
            min_length=1,
            max_length=63,
            pattern=r"^[A-Za-z0-9]([A-Za-z0-9._-]{0,61}[A-Za-z0-9])?$",
        ),
    ],
) -> ClusterRegionResponse:
    """
    Return region information for the SKR identified by the given shoot-id.

    The response is sourced from the Runtime CR in KCP and cached in Redis
    for 3 days.
    """
    logger.info(f"Cluster region request: shoot_id={shoot_id}")
    try:
        result = await get_cluster_region(shoot_id)
        logger.info(f"Cluster region lookup successful: shoot_id={shoot_id}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error for shoot_id={shoot_id}")
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cluster region.",
        ) from e
