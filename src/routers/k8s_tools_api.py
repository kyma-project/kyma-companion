"""
Kubernetes Tools REST API Router.

This module exposes Kubernetes agent tools as REST API endpoints by wrapping
the tools defined in src/agents/k8s/tools.
All endpoints require Kubernetes authentication headers.
"""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from agents.k8s.tools.logs import fetch_pod_logs_tool
from agents.k8s.tools.query import k8s_overview_query_tool, k8s_query_tool
from routers.common import API_PREFIX
from routers.tools_dependencies import HealthResponse, init_k8s_client
from services.k8s import IK8sClient
from utils.logging import get_logger

logger = get_logger(__name__)


# ============================================================================
# Request/Response Models
# ============================================================================


class K8sQueryRequest(BaseModel):
    """Request model for K8s resource query."""

    uri: str = Field(
        ...,
        description="Kubernetes API URI path (e.g., '/api/v1/namespaces/default/pods')",
        examples=[
            "/api/v1/namespaces/default/pods",
            "/apis/apps/v1/namespaces/default/deployments",
        ],
    )


class K8sQueryResponse(BaseModel):
    """Response model for K8s resource query."""

    data: dict | list[dict] = Field(..., description="Query result data")


class PodLogsRequest(BaseModel):
    """Request model for fetching pod logs."""

    name: str = Field(..., description="Pod name")
    namespace: str = Field(..., description="Namespace name")
    container_name: str = Field(..., description="Container name within the pod")
    is_terminated: bool = Field(
        default=False,
        description="Set to true to fetch logs from previous terminated container",
    )
    tail_lines: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Number of lines from the end of the logs to show",
    )


class PodLogsResponse(BaseModel):
    """Response model for pod logs."""

    logs: list[str] = Field(..., description="Pod log lines")
    pod_name: str = Field(..., description="Pod name")
    container_name: str = Field(..., description="Container name")
    line_count: int = Field(..., description="Number of log lines returned")


class K8sOverviewRequest(BaseModel):
    """Request model for K8s cluster/namespace overview."""

    namespace: str = Field(
        default="",
        description='Namespace name. Use empty string "" for cluster-level overview',
    )
    resource_kind: str = Field(
        default="cluster",
        description='Resource kind: "cluster" for cluster overview, "namespace" for namespace overview',
    )


class K8sOverviewResponse(BaseModel):
    """Response model for K8s overview."""

    context: str = Field(..., description="Contextual information in YAML format")


# ============================================================================
# Router
# ============================================================================

router = APIRouter(
    prefix=f"{API_PREFIX}/k8s-tools",
    tags=["k8s-tools"],
)


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint for the K8s Tools API.
    """
    return HealthResponse(
        status="healthy",
        message="K8s Tools API is operational",
    )


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
        result = await k8s_query_tool.ainvoke(
            {"uri": request.uri, "k8s_client": k8s_client}
        )
        logger.info(f"K8s query completed successfully for uri={request.uri}")
        return K8sQueryResponse(data=result)
    except Exception as e:
        logger.exception(f"Error during K8s query: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"K8s query failed: {str(e)}",
        ) from e


@router.post("/logs", response_model=PodLogsResponse)
async def get_pod_logs(
    request: Annotated[PodLogsRequest, Body()],
    k8s_client: Annotated[IK8sClient, Depends(init_k8s_client)],
) -> PodLogsResponse:
    """
    Fetch logs from a Kubernetes pod container.
    """
    logger.info(
        f"Pod logs request: pod={request.name}, namespace={request.namespace}, "
        f"container={request.container_name}, terminated={request.is_terminated}"
    )

    try:
        # Use fetch_pod_logs_tool from agents/k8s/tools/logs.py
        logs = await fetch_pod_logs_tool.ainvoke(
            {
                "name": request.name,
                "namespace": request.namespace,
                "container_name": request.container_name,
                "is_terminated": request.is_terminated,
                "k8s_client": k8s_client,
            }
        )

        logger.info(
            f"Successfully fetched {len(logs)} log lines for pod={request.name}"
        )

        return PodLogsResponse(
            logs=logs,
            pod_name=request.name,
            container_name=request.container_name,
            line_count=len(logs),
        )
    except Exception as e:
        logger.exception(f"Error fetching pod logs: {str(e)}")
        raise HTTPException(
            status_code=500,
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
    logger.info(
        f"K8s overview request: namespace={request.namespace}, "
        f"resource_kind={request.resource_kind}"
    )

    try:
        # Use k8s_overview_query_tool from agents/k8s/tools/query.py
        context = await k8s_overview_query_tool.ainvoke(
            {
                "namespace": request.namespace,
                "resource_kind": request.resource_kind,
                "k8s_client": k8s_client,
            }
        )

        logger.info(
            f"Successfully retrieved overview for namespace={request.namespace}"
        )

        return K8sOverviewResponse(context=context)
    except Exception as e:
        logger.exception(f"Error getting K8s overview: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get K8s overview: {str(e)}",
        ) from e
