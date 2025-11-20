"""
RAG API Router for exposing RAG search functionality via HTTP endpoints.
This allows external MCP servers to query Kyma documentation.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, Field

from rag.system import Query, RAGSystem
from routers.common import API_PREFIX
from utils.config import get_config
from utils.logging import get_logger
from utils.models.factory import ModelFactory

logger = get_logger(__name__)


class SearchRequest(BaseModel):
    """Request model for RAG search."""

    query: str = Field(..., description="The search query text")
    top_k: int = Field(
        default=5, ge=1, le=20, description="Number of results to return"
    )


class DocumentResult(BaseModel):
    """A single document result from RAG search."""

    content: str = Field(..., description="The document content")
    metadata: dict = Field(default_factory=dict, description="Document metadata")


class SearchResponse(BaseModel):
    """Response model for RAG search."""

    query: str = Field(..., description="The original query")
    documents: list[DocumentResult] = Field(
        ..., description="List of relevant documents"
    )
    count: int = Field(..., description="Number of documents returned")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Health status")
    message: str = Field(..., description="Status message")


@lru_cache(maxsize=1)
def get_rag_system() -> RAGSystem:
    """
    Initialize and cache the RAG system instance.
    This ensures we only create one instance of the RAG system.
    """
    try:
        config = get_config()
        model_factory = ModelFactory(config=config)
        models = model_factory.create_models()
        return RAGSystem(models)
    except Exception as e:
        logger.exception("Failed to initialize RAG system")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize RAG system: {str(e)}",
        ) from e


router = APIRouter(
    prefix=f"{API_PREFIX}/rag",
    tags=["rag"],
)


@router.get("/health", response_model=HealthResponse)
async def health_check(
    rag_system: Annotated[RAGSystem, Depends(get_rag_system)],
) -> HealthResponse:
    """
    Health check endpoint for the RAG API.
    Returns the status of the RAG system.
    """
    return HealthResponse(
        status="healthy",
        message="RAG system is operational",
    )


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    request: Annotated[SearchRequest, Body()],
    rag_system: Annotated[RAGSystem, Depends(get_rag_system)],
) -> SearchResponse:
    """
    Search Kyma documentation using RAG (Retrieval-Augmented Generation).

    This endpoint performs semantic search across indexed Kyma documentation
    and returns the most relevant document chunks.

    Args:
        request: Search request containing query text and number of results
        rag_system: Injected RAG system instance

    Returns:
        SearchResponse containing relevant document chunks

    Raises:
        HTTPException: If search fails or encounters an error
    """
    logger.info(f"RAG search request: query='{request.query}', top_k={request.top_k}")

    try:
        # Create query object
        query = Query(text=request.query)

        # Perform RAG retrieval
        documents = await rag_system.aretrieve(query, top_k=request.top_k)

        # Convert LangChain documents to API response format
        document_results = [
            DocumentResult(
                content=doc.page_content,
                metadata=doc.metadata,
            )
            for doc in documents
        ]

        logger.info(f"RAG search completed: found {len(document_results)} documents")

        return SearchResponse(
            query=request.query,
            documents=document_results,
            count=len(document_results),
        )

    except Exception as e:
        logger.exception(f"Error during RAG search: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"RAG search failed: {str(e)}",
        ) from e


@router.get("/topics")
async def list_topics() -> dict:
    """
    List available documentation topics/sources.

    Returns information about the Kyma components and documentation
    sources that are indexed in the RAG system.

    Returns:
        Dictionary containing available topics and components
    """
    # This can be expanded to dynamically list indexed topics
    # For now, returning static information based on docs_sources.json
    topics = [
        "api-gateway",
        "eventing-manager",
        "serverless",
        "telemetry-manager",
        "btp-manager",
        "istio",
        "nats-manager",
        "warden",
        "cloud-manager",
        "application-connector-manager",
        "docker-registry",
        "keda-manager",
        "busola",
    ]

    return {
        "topics": topics,
        "count": len(topics),
        "description": "Available Kyma components with indexed documentation",
    }
