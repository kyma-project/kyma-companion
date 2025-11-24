"""
Shared dependencies for K8s and Kyma Tools API routers.

This module contains common dependency functions and models used by both
k8s_tools_api.py and kyma_tools_api.py to avoid code duplication.
"""

from typing import Annotated

from fastapi import Depends, Header, HTTPException
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel, Field

from services.data_sanitizer import DataSanitizer, IDataSanitizer
from services.k8s import IK8sClient, K8sAuthHeaders, K8sClient
from utils.config import Config, get_config
from utils.logging import get_logger
from utils.models.factory import IModel, ModelFactory

logger = get_logger(__name__)


# ============================================================================
# Shared Response Models
# ============================================================================


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Health status")
    message: str = Field(..., description="Status message")


# ============================================================================
# Shared Dependencies
# ============================================================================


def init_config() -> Config:
    """Initialize the config object."""
    return get_config()


def init_data_sanitizer(
    config: Annotated[Config, Depends(init_config)],
) -> IDataSanitizer:
    """Initialize the data sanitizer instance."""
    return DataSanitizer(config.sanitization_config)


# Cache for models dict to avoid recreating on every request
_models_cache: dict[str, IModel | Embeddings] | None = None


def init_models_dict(
    config: Annotated[Config, Depends(init_config)],
) -> dict[str, IModel | Embeddings]:
    """
    Initialize models dictionary from config.
    """
    global _models_cache

    if _models_cache is None:
        try:
            model_factory = ModelFactory(config=config)
            _models_cache = model_factory.create_models()
        except Exception as e:
            logger.exception("Failed to initialize models")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize models: {str(e)}",
            ) from e

    return _models_cache


def init_k8s_client(
    x_cluster_url: Annotated[str, Header()],
    x_cluster_certificate_authority_data: Annotated[str, Header()],
    data_sanitizer: Annotated[IDataSanitizer, Depends(init_data_sanitizer)],
    x_k8s_authorization: Annotated[str, Header()] = None,  # type: ignore[assignment]
    x_client_certificate_data: Annotated[str, Header()] = None,  # type: ignore[assignment]
    x_client_key_data: Annotated[str, Header()] = None,  # type: ignore[assignment]
) -> IK8sClient:
    """
    Initialize K8s client with authentication headers.

    Required headers:
    - x-cluster-url: Kubernetes cluster URL
    - x-cluster-certificate-authority-data: Base64 encoded CA certificate

    Authentication (one of):
    - x-k8s-authorization: Bearer token
    - x-client-certificate-data & x-client-key-data: Client certificates
    """
    k8s_auth_headers = K8sAuthHeaders(
        x_cluster_url=x_cluster_url,
        x_cluster_certificate_authority_data=x_cluster_certificate_authority_data,
        x_k8s_authorization=x_k8s_authorization,
        x_client_certificate_data=x_client_certificate_data,
        x_client_key_data=x_client_key_data,
    )

    try:
        k8s_auth_headers.validate_headers()
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    try:
        return K8sClient(
            k8s_auth_headers=k8s_auth_headers,
            data_sanitizer=data_sanitizer,
        )
    except Exception as e:
        logger.error(f"Failed to initialize K8s client: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to connect to the cluster: {str(e)}",
        ) from e
