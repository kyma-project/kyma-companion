"""
Service for fetching cluster region information from KCP Runtime CRs.

Fetches the Runtime CR for a given shoot-id from the local Kubernetes cluster
(KCP), extracts region/platformRegion/provider labels, and caches the result
in Redis for 3 days.
"""

from http import HTTPStatus

from kubernetes import client, config, dynamic
from kubernetes.client.rest import ApiException

from routers.common import ClusterRegionResponse
from services.redis import get_redis
from utils.logging import get_logger

logger = get_logger(__name__)

# Labels on the Runtime CR
_LABEL_SHOOT_NAME = "kyma-project.io/shoot-name"
_LABEL_REGION = "kyma-project.io/region"
_LABEL_PLATFORM_REGION = "kyma-project.io/platform-region"
_LABEL_PROVIDER = "kyma-project.io/provider"

# EU-Access platform regions
_EU_ACCESS_PLATFORM_REGIONS = frozenset(["cf-eu11", "cf-ch20", "cf-eu01", "cf-eu02", "cf-eu31"])

# KCP namespace where Runtime CRs live
_KCP_NAMESPACE = "kcp-system"

# Runtime CR group/version/plural
_RUNTIME_GROUP = "infrastructuremanager.kyma-project.io"
_RUNTIME_VERSION = "v1"

# Redis cache TTL: 3 days in seconds
_CACHE_TTL_SECONDS = 3 * 24 * 60 * 60

# Redis key prefix
_CACHE_KEY_PREFIX = "cluster-region:"


def _cache_key(shoot_id: str) -> str:
    return f"{_CACHE_KEY_PREFIX}{shoot_id}"


def _build_response(shoot_id: str, labels: dict) -> ClusterRegionResponse:
    platform_region = labels.get(_LABEL_PLATFORM_REGION, "")
    return ClusterRegionResponse(
        **{
            "shoot-id": shoot_id,
            "region": labels.get(_LABEL_REGION, ""),
            "platformRegion": platform_region,
            "provider": labels.get(_LABEL_PROVIDER, ""),
            "isEUAccessOnly": platform_region in _EU_ACCESS_PLATFORM_REGIONS,
        }
    )


def _get_dynamic_client() -> dynamic.DynamicClient:
    """Load k8s config (in-cluster when deployed, local kubeconfig otherwise)."""
    conf = client.Configuration()
    try:
        config.load_incluster_config(client_configuration=conf)
    except config.ConfigException:
        config.load_kube_config(client_configuration=conf)
    return dynamic.DynamicClient(client.ApiClient(configuration=conf))


async def get_cluster_region(shoot_id: str) -> ClusterRegionResponse:
    """
    Return cluster region info for the given shoot-id.

    Checks Redis cache first; on a miss, queries the KCP Runtime CR by
    label selector, caches the result for 3 days, and returns it.

    Raises:
        HTTPException (404) if no Runtime CR is found for the shoot-id.
        HTTPException (500) for unexpected errors.
    """
    from fastapi import HTTPException

    redis = get_redis()

    # --- Cache lookup ---
    if redis.has_connection():
        try:
            cached = await redis.get_connection().get(_cache_key(shoot_id))
            if cached:
                logger.debug(f"Cache hit for shoot_id={shoot_id}")
                return ClusterRegionResponse.model_validate_json(cached)
        except Exception:
            logger.warning(f"Redis read failed for shoot_id={shoot_id}, proceeding without cache")

    # --- Fetch from KCP ---
    logger.info(f"Cache miss for shoot_id={shoot_id}, fetching Runtime CR")
    try:
        dynamic_client = _get_dynamic_client()
        resource_api = dynamic_client.resources.get(
            api_version=f"{_RUNTIME_GROUP}/{_RUNTIME_VERSION}",
            kind="Runtime",
        )
        result = resource_api.get(
            namespace=_KCP_NAMESPACE,
            label_selector=f"{_LABEL_SHOOT_NAME}={shoot_id}",
        )
    except ApiException as e:
        logger.exception(f"Kubernetes API error fetching Runtime CR for shoot_id={shoot_id}")
        raise HTTPException(
            status_code=e.status if isinstance(e.status, int) else HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Runtime CR: {e.reason}",
        ) from e
    except Exception as e:
        logger.exception(f"Unexpected error fetching Runtime CR for shoot_id={shoot_id}")
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Failed to fetch Runtime CR.",
        ) from e

    items = getattr(result, "items", [])
    if not items:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"Runtime CR not found for shoot-id '{shoot_id}'",
        )

    if len(items) > 1:
        logger.error(f"Multiple Runtime CRs found for shoot_id={shoot_id} (count={len(items)})")
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Multiple Runtime CRs found for shoot-id '{shoot_id}'",
        )

    labels: dict = items[0].get("metadata", {}).get("labels", {}) or {}
    response = _build_response(shoot_id, labels)

    # --- Write to cache ---
    if redis.has_connection():
        try:
            await redis.get_connection().setex(
                _cache_key(shoot_id),
                _CACHE_TTL_SECONDS,
                response.model_dump_json(by_alias=True),
            )
            logger.debug(f"Cached cluster region for shoot_id={shoot_id}")
        except Exception:
            logger.warning(f"Redis write failed for shoot_id={shoot_id}, continuing without cache")

    return response
