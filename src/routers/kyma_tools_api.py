"""
Kyma Tools REST API Router.

This module exposes Kyma agent tools as REST API endpoints by wrapping
the tools defined in src/agents/kyma/tools.
"""

from typing import Annotated

from fastapi import APIRouter, Body, Depends
from langchain_core.embeddings import Embeddings

from agents.kyma.tools.query import (
    fetch_kyma_resource_version,
    kyma_query_tool,
)
from agents.kyma.tools.search import SearchKymaDocTool
from routers.common import (
    API_PREFIX,
    KymaQueryRequest,
    KymaQueryResponse,
    KymaResourceVersionRequest,
    KymaResourceVersionResponse,
    SearchKymaDocRequest,
    SearchKymaDocResponse,
    init_k8s_client,
    init_models_dict,
)
from routers.error_handlers import handle_tool_errors
from services.k8s import IK8sClient
from utils.logging import get_logger
from utils.models.factory import IModel

logger = get_logger(__name__)


# ============================================================================
# Router
# ============================================================================

router = APIRouter(
    prefix=f"{API_PREFIX}/tools/kyma",
    tags=["kyma-tools"],
)


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/query", response_model=KymaQueryResponse)
@handle_tool_errors("Kyma query")
async def query_kyma_resource(
    request: Annotated[KymaQueryRequest, Body()],
    k8s_client: Annotated[IK8sClient, Depends(init_k8s_client)],
) -> KymaQueryResponse:
    """
    Query Kyma resources using the Kubernetes API.
    """
    logger.info(f"Kyma query request: uri={request.uri}")

    result = await kyma_query_tool.ainvoke({"uri": request.uri, "k8s_client": k8s_client})
    logger.info(f"Kyma query completed successfully for uri={request.uri}")
    return KymaQueryResponse(data=result)


@router.post("/resource-version", response_model=KymaResourceVersionResponse)
@handle_tool_errors("Kyma resource version lookup")
async def get_resource_version(
    request: Annotated[KymaResourceVersionRequest, Body()],
    k8s_client: Annotated[IK8sClient, Depends(init_k8s_client)],
) -> KymaResourceVersionResponse:
    """
    Fetch the API version for a Kyma resource kind.
    """
    logger.info(f"Resource version request: kind={request.resource_kind}")

    api_version = fetch_kyma_resource_version.invoke(
        {
            "resource_kind": request.resource_kind,
            "k8s_client": k8s_client,
        }
    )
    logger.info(f"Resource version lookup successful: kind={request.resource_kind}, version={api_version}")
    return KymaResourceVersionResponse(
        resource_kind=request.resource_kind,
        api_version=api_version,
    )


@router.post("/search", response_model=SearchKymaDocResponse)
@handle_tool_errors("Kyma documentation search")
async def search_kyma_documentation(
    request: Annotated[SearchKymaDocRequest, Body()],
    models: Annotated[dict[str, IModel | Embeddings], Depends(init_models_dict)],
) -> SearchKymaDocResponse:
    """
    Search Kyma documentation using semantic search.
    """
    logger.info(f"Search request: query={request.query}")

    search_tool = SearchKymaDocTool(models=models, top_k=request.top_k)
    results = await search_tool.arun_list(query=request.query)
    logger.info(f"Search completed successfully, returned {len(results)} documents")
    return SearchKymaDocResponse(
        results=results,
        query=request.query,
    )
