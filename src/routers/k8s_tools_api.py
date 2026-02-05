"""
Kubernetes Tools REST API Router.

This module exposes Kubernetes agent tools as REST API endpoints by wrapping
the tools defined in src/agents/k8s/tools.
All endpoints require Kubernetes authentication headers.
"""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException

from agents.k8s.tools.logs import fetch_pod_logs_tool
from agents.k8s.tools.query import k8s_overview_query_tool, k8s_query_tool
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
from utils.exceptions import K8sClientError
from utils.logging import get_logger

logger = get_logger(__name__)


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
        # Use k8s_query_tool from agents/k8s/tools/query.py
        result = await k8s_query_tool.ainvoke({"uri": request.uri, "k8s_client": k8s_client})
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
) -> PodLogsResponse:
    """
    Fetch logs from a Kubernetes pod container.
    """
    logger.info(
        f"Pod logs request: pod={request.name}, namespace={request.namespace}, container={request.container_name}"
    )

    try:
        result = await fetch_pod_logs_tool.ainvoke(
            {
                "name": request.name,
                "namespace": request.namespace,
                "container_name": request.container_name,
                "k8s_client": k8s_client,
            }
        )

        logger.info(f"Successfully fetched logs for pod={request.name}")

        # Tool returns dict (serialized Pydantic model), reconstruct for response
        pod_logs_result = PodLogsResult.model_validate(result)

        return PodLogsResponse(
            logs=pod_logs_result.logs,
            diagnostic_context=pod_logs_result.diagnostic_context,
            pod_name=request.name,
            container_name=request.container_name,
        )
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
        # Use k8s_overview_query_tool from agents/k8s/tools/query.py
        context = await k8s_overview_query_tool.ainvoke(
            {
                "namespace": request.namespace,
                "resource_kind": request.resource_kind,
                "k8s_client": k8s_client,
            }
        )

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
