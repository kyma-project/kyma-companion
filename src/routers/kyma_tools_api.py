"""
Kyma Tools REST API Router.

This module exposes Kyma agent tools as REST API endpoints by wrapping
the tools defined in src/agents/kyma/tools.
All endpoints require Kubernetes authentication headers.
"""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel, Field

from agents.kyma.tools.query import (
    fetch_kyma_resource_version,
    kyma_query_tool,
)
from agents.kyma.tools.search import SearchKymaDocTool
from routers.common import API_PREFIX
from routers.tools_dependencies import (
    HealthResponse,
    init_k8s_client,
    init_models_dict,
)
from services.k8s import IK8sClient
from utils.logging import get_logger
from utils.models.factory import IModel

logger = get_logger(__name__)


# ============================================================================
# Request/Response Models
# ============================================================================


class KymaQueryRequest(BaseModel):
    """Request model for Kyma resource query."""

    uri: str = Field(
        ...,
        description="Kubernetes API URI path for Kyma resources",
        examples=[
            "/apis/serverless.kyma-project.io/v1alpha2/namespaces/default/functions",
            "/apis/gateway.kyma-project.io/v1beta1/namespaces/default/apirules",
            "/apis/eventing.kyma-project.io/v1alpha2/namespaces/default/subscriptions",
        ],
    )


class KymaQueryResponse(BaseModel):
    """Response model for Kyma resource query."""

    data: dict | list[dict] = Field(..., description="Query result data")


class KymaResourceVersionRequest(BaseModel):
    """Request model for fetching Kyma resource version."""

    resource_kind: str = Field(
        ...,
        description="Kyma resource kind (e.g., 'Function', 'APIRule', 'TracePipeline')",
        examples=[
            "Function",
            "APIRule",
            "ServiceInstance",
            "TracePipeline",
            "Subscription",
        ],
    )


class KymaResourceVersionResponse(BaseModel):
    """Response model for Kyma resource version."""

    resource_kind: str = Field(..., description="Resource kind")
    api_version: str = Field(..., description="API version (e.g., 'group/version')")


class SearchKymaDocRequest(BaseModel):
    """Request model for searching Kyma documentation."""

    query: str = Field(
        ...,
        description="Search query for Kyma documentation",
        examples=[
            "How to install Kyma?",
            "What are Kyma components?",
            "How to troubleshoot Kyma Istio module?",
        ],
    )


class SearchKymaDocResponse(BaseModel):
    """Response model for Kyma documentation search."""

    results: str = Field(..., description="Retrieved documentation content")
    query: str = Field(..., description="Original search query")


# ============================================================================
# Router
# ============================================================================

router = APIRouter(
    prefix=f"{API_PREFIX}/kyma-tools",
    tags=["kyma-tools"],
)


# ============================================================================
# Endpoints
# ============================================================================


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint for the Kyma Tools API.
    Returns the operational status of the API.
    """
    return HealthResponse(
        status="healthy",
        message="Kyma Tools API is operational",
    )


@router.post("/query", response_model=KymaQueryResponse)
async def query_kyma_resource(
    request: Annotated[KymaQueryRequest, Body()],
    k8s_client: Annotated[IK8sClient, Depends(init_k8s_client)],
) -> KymaQueryResponse:
    """
    Query Kyma custom resources in the cluster.
    """
    logger.info(f"Kyma query request: uri={request.uri}")

    try:
        # Use kyma_query_tool from agents/kyma/tools/query.py
        result = await kyma_query_tool.ainvoke({"uri": request.uri, "k8s_client": k8s_client})
        logger.info(f"Kyma query completed successfully for uri={request.uri}")
        return KymaQueryResponse(data=result)
    except Exception as e:
        logger.exception(f"Error during Kyma query: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Kyma query failed: {str(e)}",
        ) from e


@router.post("/resource-version", response_model=KymaResourceVersionResponse)
async def get_kyma_resource_version(
    request: Annotated[KymaResourceVersionRequest, Body()],
    k8s_client: Annotated[IK8sClient, Depends(init_k8s_client)],
) -> KymaResourceVersionResponse:
    """
    Get the API version for a Kyma resource kind.
    """
    logger.info(f"Kyma resource version request: kind={request.resource_kind}")

    try:
        # Use fetch_kyma_resource_version from agents/kyma/tools/query.py
        api_version = fetch_kyma_resource_version.invoke(
            {
                "resource_kind": request.resource_kind,
                "k8s_client": k8s_client,
            }
        )
        logger.info(f"Successfully retrieved API version for {request.resource_kind}: {api_version}")
        return KymaResourceVersionResponse(
            resource_kind=request.resource_kind,
            api_version=api_version,
        )
    except Exception as e:
        logger.exception(f"Error getting resource version: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=(f"Failed to get resource version for '{request.resource_kind}': {str(e)}"),
        ) from e


@router.post("/search", response_model=SearchKymaDocResponse)
async def search_kyma_documentation(
    request: Annotated[SearchKymaDocRequest, Body()],
    models: Annotated[dict[str, IModel | Embeddings], Depends(init_models_dict)],
) -> SearchKymaDocResponse:
    """
    Search through Kyma documentation for relevant information.
    """
    logger.info(f"Kyma doc search request: query={request.query}")

    try:
        # Use SearchKymaDocTool from /agents/kyma/tools/search.py
        search_tool = SearchKymaDocTool(models=models, top_k=5)

        # Execute the search
        results = await search_tool._arun(query=request.query)

        logger.info(f"Kyma doc search completed for query={request.query}")

        return SearchKymaDocResponse(
            results=results,
            query=request.query,
        )
    except Exception as e:
        logger.exception(f"Error searching Kyma documentation: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search Kyma documentation: {str(e)}",
        ) from e
