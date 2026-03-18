"""
Kubernetes Tools REST API Router.

This module exposes Kubernetes agent tools as REST API endpoints.
All endpoints require Kubernetes authentication headers.
"""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Response

from agents.common.data import Message
from agents.common.utils import get_relevant_context_from_k8s_cluster
from routers.common import (
    API_PREFIX,
    K8sOverviewRequest,
    K8sOverviewResponse,
    K8sQueryRequest,
    K8sQueryResponse,
    PodLogsRequest,
    PodLogsResponse,
    init_k8s_client,
)
from services.k8s import IK8sClient
from services.k8s_models import PodLogsResult
from utils.exceptions import K8sClientError, NoLogsAvailableError
from utils.logging import get_logger

logger = get_logger(__name__)

POD_LOGS_TAIL_LINES_LIMIT: int = 10

# ============================================================================
# Router
# ============================================================================

router = APIRouter(
    prefix=f"{API_PREFIX}/tools/k8s",
    tags=["k8s-tools"],
)


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/query", response_model=K8sQueryResponse)
async def query_k8s_resource(
    request: Annotated[K8sQueryRequest, Body()],
    k8s_client: Annotated[IK8sClient, Depends(init_k8s_client)],
) -> K8sQueryResponse:
    """
    Query Kubernetes resources using the Kubernetes API.
    """
    logger.info(f"K8s query request: uri={request.uri}")

    try:
        result = await k8s_client.execute_get_api_request(request.uri)
        logger.info(f"K8s query completed successfully for uri={request.uri}")
        return K8sQueryResponse(data=result)
    except K8sClientError as e:
        logger.error(f"K8s API error for uri={request.uri}: {e.status_code} - {e.message}")
        raise HTTPException(
            status_code=e.status_code,
            detail=f"Kubernetes API error: {e.message}",
        ) from e
    except Exception as e:
        logger.exception(f"Error during K8s query for uri={request.uri}: {str(e)}")
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"K8s query failed: {str(e)}",
        ) from e


@router.post("/pods/logs", response_model=PodLogsResponse, response_model_exclude_none=True)
async def get_pod_logs(
    request: Annotated[PodLogsRequest, Body()],
    k8s_client: Annotated[IK8sClient, Depends(init_k8s_client)],
    response: Response,
) -> PodLogsResponse:
    """
    Fetch logs from a Kubernetes pod container.
    """
    logger.info(
        f"Pod logs request: pod={request.name}, namespace={request.namespace}, container={request.container_name}"
    )

    try:
        pod_logs_result = await k8s_client.fetch_pod_logs(
            request.name,
            request.namespace,
            request.container_name,
            POD_LOGS_TAIL_LINES_LIMIT,
        )

        logger.info(f"Successfully fetched logs for pod={request.name}")

        # Forward the status code from K8s API (e.g., 400 for invalid container)
        response.status_code = pod_logs_result.status_code

    except NoLogsAvailableError as e:
        logger.warning(
            f"No log data or diagnostic info available for pod={request.name}, "
            f"namespace={request.namespace}, container={request.container_name}"
        )
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail=e.message,
        ) from e
    except K8sClientError as e:
        logger.error(
            f"K8s error fetching logs for pod={request.name}, "
            f"namespace={request.namespace}: {e.status_code} - {e.message}"
        )
        raise HTTPException(
            status_code=e.status_code,
            detail=f"Kubernetes error: {e.message}",
        ) from e
    except Exception as e:
        logger.exception(f"Error fetching logs for pod={request.name}, namespace={request.namespace}: {str(e)}")
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch pod logs: {str(e)}",
        ) from e

    return PodLogsResponse(
        logs=pod_logs_result.logs,
        diagnostic_context=pod_logs_result.diagnostic_context,
        pod_name=request.name,
        container_name=request.container_name,
    )


@router.post("/overview", response_model=K8sOverviewResponse)
async def get_k8s_overview(
    request: Annotated[K8sOverviewRequest, Body()],
    k8s_client: Annotated[IK8sClient, Depends(init_k8s_client)],
) -> K8sOverviewResponse:
    """
    Get an overview of the Kubernetes cluster or namespace.
    """
    logger.info(f"K8s overview request: namespace={request.namespace}, resource_kind={request.resource_kind}")

    try:
        message = Message(
            resource_kind=request.resource_kind,
            namespace=request.namespace,
            query="",
            resource_api_version="",
            resource_name="",
        )
        context = await get_relevant_context_from_k8s_cluster(message, k8s_client)

        logger.info(f"Successfully retrieved overview for namespace={request.namespace}")

        return K8sOverviewResponse(context=context)
    except K8sClientError as e:
        logger.error(
            f"K8s error for namespace={request.namespace}, "
            f"resource_kind={request.resource_kind}: {e.status_code} - {e.message}"
        )
        raise HTTPException(
            status_code=e.status_code,
            detail=f"Kubernetes error: {e.message}",
        ) from e
    except Exception as e:
        logger.exception(
            f"Error getting overview for namespace={request.namespace}, resource_kind={request.resource_kind}: {str(e)}"
        )
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=f"Failed to get K8s overview: {str(e)}",
        ) from e
