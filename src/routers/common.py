"""
Common models, constants, and dependencies shared across routers.
"""

import base64
import json
from http import HTTPStatus
from typing import Annotated

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import Depends, Header, HTTPException
from langchain_core.embeddings import Embeddings
from pydantic import BaseModel, Field

from services.data_sanitizer import DataSanitizer, IDataSanitizer
from services.k8s import IK8sClient, K8sAuthHeaders, K8sClient
from services.k8s_models import PodLogs, PodLogsDiagnosticContext
from utils.config import Config, get_config
from utils.logging import get_logger
from utils.models.factory import IModel, ModelFactory
from utils.settings import RSA_PRIVATE_KEY

logger = get_logger(__name__)


# ============================================================================
# Constants
# ============================================================================

SESSION_ID_HEADER = "session-id"
API_PREFIX = "/api"


# ============================================================================
# Conversation Models
# ============================================================================


class InitConversationBody(BaseModel):
    """Request body for initializing a conversation endpoint."""

    resource_kind: str
    resource_name: str = ""
    resource_api_version: str = ""
    namespace: str = ""


class InitialQuestionsResponse(BaseModel):
    """Response body for initializing a conversation endpoint"""

    initial_questions: list[str] = []
    conversation_id: str


class FollowUpQuestionsResponse(BaseModel):
    """Response body for follow-up questions endpoint"""

    questions: list[str] = []


# ============================================================================
# Health/Probe Models
# ============================================================================


class ReadinessModel(BaseModel):
    """Response body representing the state of the Liveness Probe"""

    is_redis_initialized: bool
    is_hana_initialized: bool
    are_models_initialized: bool


class HealthModel(BaseModel):
    """Response body representing the state of the Readiness Probe"""

    is_redis_healthy: bool
    is_hana_healthy: bool
    is_usage_tracker_healthy: bool
    llms: dict[str, bool]


# ============================================================================
# K8s Tools Models
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
    container_name: str = Field(default="", description="Container name within the pod")
    tail_lines: int = Field(
        default=10,
        ge=1,
        le=1000,
        description="Number of lines from the end of the logs to show",
    )


class PodLogsResponse(BaseModel):
    """Response model for pod logs."""

    logs: PodLogs = Field(
        ...,
        description="Container logs with current_container and previously_terminated_container",
    )
    diagnostic_context: PodLogsDiagnosticContext | None = Field(
        default=None,
        description="Optional diagnostic information when current pod logs are unavailable",
    )
    pod_name: str = Field(..., description="Pod name")
    container_name: str = Field(..., description="Container name")


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
# Kyma Tools Models
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
            "Help me get started with kyma",
            "What are Kyma components?",
            "How to troubleshoot Kyma Istio module?",
        ],
    )
    top_k: int = Field(
        default=5,
        description="Number of top documents to return",
        ge=1,
        le=50,
    )


class SearchKymaDocResponse(BaseModel):
    """Response model for Kyma documentation search."""

    results: list[str] = Field(..., description="List of retrieved documents")
    query: str = Field(..., description="Original search query")


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


class _ModelsCache:
    """Singleton cache for models dict to avoid using global statement."""

    _instance: dict[str, IModel | Embeddings] | None = None


def init_models_dict(
    config: Annotated[Config, Depends(init_config)],
) -> dict[str, IModel | Embeddings]:
    """
    Initialize models dictionary from config.

    Creates a dict of model_name -> model instance for use by tools
    that require LLM models and embeddings.
    Uses a class-level cache to avoid recreating models on every request.
    """
    if _ModelsCache._instance is None:
        try:
            model_factory = ModelFactory(config=config)
            _ModelsCache._instance = model_factory.create_models()
        except Exception as e:
            logger.exception("Failed to initialize models")
            raise HTTPException(
                status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
                detail=f"Failed to initialize models: {str(e)}",
            ) from e

    return _ModelsCache._instance


def init_k8s_client(
    data_sanitizer: Annotated[IDataSanitizer, Depends(init_data_sanitizer)],
    x_cluster_url: Annotated[str, Header()] = None,  # type: ignore[assignment]
    x_cluster_certificate_authority_data: Annotated[str, Header()] = None,  # type: ignore[assignment]
    x_k8s_authorization: Annotated[str, Header()] = None,  # type: ignore[assignment]
    x_client_certificate_data: Annotated[str, Header()] = None,  # type: ignore[assignment]
    x_client_key_data: Annotated[str, Header()] = None,  # type: ignore[assignment]
    x_encrypted_key: Annotated[str, Header()] = None,  # type: ignore[assignment]
    x_client_iv: Annotated[str, Header()] = None,  # type: ignore[assignment]
    x_target_cluster_encrypted: Annotated[str, Header()] = None,  # type: ignore[assignment]
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


    
    if x_encrypted_key and x_client_iv and x_target_cluster_encrypted and RSA_PRIVATE_KEY:
        try:
            # Decode the base64-encoded RSA private key and load it
            private_key_pem = base64.b64decode(RSA_PRIVATE_KEY)
            private_key = serialization.load_pem_private_key(
                private_key_pem,
                password=None,
                backend=default_backend(),
            )

            # Decode the base64-encoded encrypted AES key
            encrypted_aes_key = base64.b64decode(x_encrypted_key)

            # Decrypt the AES-256 key using RSA-OAEP
            aes_key = private_key.decrypt(
                encrypted_aes_key,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )

            # Decode the base64-encoded IV and ciphertext
            iv = base64.b64decode(x_client_iv)
            ciphertext = base64.b64decode(x_target_cluster_encrypted)

            # Decrypt the target cluster data using AES-GCM
            aesgcm = AESGCM(aes_key)
            decrypted_data = aesgcm.decrypt(iv, ciphertext, None)

            # Parse the decrypted JSON data
            cluster_data = json.loads(decrypted_data.decode("utf-8"))

            # Extract cluster credentials from decrypted data
            x_cluster_url = cluster_data.get("cluster_url", "")
            x_cluster_certificate_authority_data = cluster_data.get(
                "cluster_certificate_authority_data", ""
            )
            x_k8s_authorization = cluster_data.get("k8s_authorization", "")
            x_client_certificate_data = cluster_data.get(
                "client_certificate_data", None
            )
            x_client_key_data = cluster_data.get("client_key_data", None)

        except Exception as e:
            logger.exception("Failed to decrypt cluster credentials")
            raise HTTPException(
                status_code=HTTPStatus.BAD_REQUEST,
                detail=f"Failed to decrypt cluster credentials: {str(e)}",
            ) from e

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

    # Note: K8sClient initialization doesn't immediately validate connection
    # Connection validation is deferred until first API call (lazy initialization)
    # This allows authentication errors to be caught by route handlers
    return K8sClient(
        k8s_auth_headers=k8s_auth_headers,
        data_sanitizer=data_sanitizer,
    )
