"""
Evaluation tests for K8s and Kyma Tools API endpoints using encrypted headers.

These tests replicate the test_tools_api test suite but authenticate using
ECDH + AES-256-GCM encrypted headers instead of plain-text credentials.

The ECDH key exchange and payload encryption are performed once per module:
- POST /api/public-key is called once to register the client public key and
  receive the companion's public key together with a session ID.
- A single AES-256 session key is derived and used to encrypt the cluster
  credentials JSON payload once.
- All tests share the same encrypted headers; the server's 5-minute replay
  window permits legitimate re-use within a single test run.
"""

import base64
import json
import logging
import os
from http import HTTPStatus

import pytest
import requests
from common.config import Config
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

logger = logging.getLogger(__name__)

# Minimum status code for client/server errors
MIN_ERROR_STATUS_CODE = 400
TIMEOUT = 120  # seconds

_ECDH_CURVE = ec.SECP256R1()
_HKDF_INFO = b"ecdh-key-exchange"
_AES_GCM_NONCE_SIZE = 12


def _encrypt_cluster_payload(
    companion_public_key_b64: str,
    client_private_key: ec.EllipticCurvePrivateKey,
    aes_key: bytes,
    key_nonce: bytes,
    iv: bytes,
    plaintext: bytes,
) -> tuple[str, str, str]:
    """Encrypt plaintext cluster credentials using ECDH + AES-256-GCM.

    Wire formats produced:
    - x_encrypted_key:  base64(key_nonce[12B] || AES-GCM(shared_key, aes_key))
    - x_client_iv:      base64(iv[12B])
    - x_target_cluster_encrypted: base64(AES-GCM(aes_key, plaintext))

    Returns (x_encrypted_key, x_client_iv, x_target_cluster_encrypted).
    """
    companion_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
        _ECDH_CURVE, base64.b64decode(companion_public_key_b64)
    )
    shared_secret = client_private_key.exchange(ec.ECDH(), companion_public_key)
    shared_key = HKDF(
        algorithm=SHA256(),
        length=32,
        salt=None,
        info=_HKDF_INFO,
    ).derive(shared_secret)

    encrypted_aes_key = AESGCM(shared_key).encrypt(key_nonce, aes_key, None)
    x_encrypted_key = base64.b64encode(key_nonce + encrypted_aes_key).decode()

    encrypted_data = AESGCM(aes_key).encrypt(iv, plaintext, None)
    x_client_iv = base64.b64encode(iv).decode()
    x_target_cluster_encrypted = base64.b64encode(encrypted_data).decode()

    return x_encrypted_key, x_client_iv, x_target_cluster_encrypted


# ---------------------------------------------------------------------------
# Module-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> Config:
    """Load configuration for tests."""
    return Config()


@pytest.fixture(scope="module")
def base_api_url(config: Config) -> str:
    """Get base API URL."""
    return config.companion_api_url


@pytest.fixture(scope="module")
def encryption_session(config: Config, base_api_url: str) -> dict:
    """Perform the ECDH key exchange once for the whole module.

    Steps:
    1. Generate a fresh client EC key pair in memory.
    2. POST /api/public-key to register the client public key and receive
       the companion public key and a session ID.
    3. Generate a single AES-256 session key to reuse across all tests.

    Returns a dict with the session data needed to encrypt headers per test.
    """
    # 1. Generate client EC key pair
    client_private_key = ec.generate_private_key(_ECDH_CURVE)
    client_public_key_b64 = base64.b64encode(
        client_private_key.public_key().public_bytes(Encoding.X962, PublicFormat.UncompressedPoint)
    ).decode()

    # 2. Register client public key, receive companion public key + session ID
    response = requests.post(
        f"{base_api_url}/api/public-key",
        json={"public_key": client_public_key_b64},
        headers={"Content-Type": "application/json"},
        timeout=TIMEOUT,
    )
    assert response.status_code == HTTPStatus.OK, f"Failed to register client public key: {response.text}"
    body = response.json()

    # 3. Build cluster credentials payload using the K8sAuthHeaders validation alias keys
    plaintext = json.dumps(
        {
            "x-cluster-url": config.test_cluster_url,
            "x-cluster-certificate-authority-data": config.test_cluster_ca_data,
            "x-k8s-authorization": config.test_cluster_auth_token,
        }
    ).encode()

    return {
        "client_private_key": client_private_key,
        "session_id": body["session_id"],
        "companion_public_key_b64": body["companion_public_key"],
        "aes_key": os.urandom(32),
        "plaintext": plaintext,
    }


@pytest.fixture
def encrypted_auth_headers(encryption_session: dict) -> dict[str, str]:
    """Build encrypted authentication headers with fresh nonces for each test.

    Reuses the AES key and session from the module-scoped ``encryption_session``
    fixture, but generates a new key_nonce and IV on every call so that no nonce
    is ever reused across requests.
    """
    key_nonce = os.urandom(_AES_GCM_NONCE_SIZE)
    iv = os.urandom(_AES_GCM_NONCE_SIZE)

    x_encrypted_key, x_client_iv, x_target_cluster_encrypted = _encrypt_cluster_payload(
        encryption_session["companion_public_key_b64"],
        encryption_session["client_private_key"],
        encryption_session["aes_key"],
        key_nonce,
        iv,
        encryption_session["plaintext"],
    )

    return {
        "Content-Type": "application/json",
        "x-encrypted-key": x_encrypted_key,
        "x-client-iv": x_client_iv,
        "x-session-id": encryption_session["session_id"],
        "x-target-cluster-encrypted": x_target_cluster_encrypted,
    }


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------


class TestK8sToolsAPI:
    """Test suite for K8s Tools API endpoints."""

    @pytest.fixture(scope="class")
    def base_url(self, base_api_url: str) -> str:
        """Get base URL for K8s Tools API requests."""
        return f"{base_api_url}/api/tools/k8s"

    def test_query_k8s_deployments(self, base_url: str, encrypted_auth_headers: dict[str, str]) -> None:
        """Test querying K8s deployments in default namespace."""
        logger.info("Testing K8s Query - List Deployments")

        response = requests.post(
            f"{base_url}/query",
            json={"uri": "/apis/apps/v1/namespaces/default/deployments"},
            headers=encrypted_auth_headers,
            timeout=TIMEOUT,
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "data" in data
        # Handle both dict and list response formats
        items = data["data"].get("items", []) if isinstance(data["data"], dict) else data["data"]
        logger.info(f"Successfully queried deployments: {len(items)} found")

    def test_query_k8s_pods(self, base_url: str, encrypted_auth_headers: dict[str, str]) -> None:
        """Test querying K8s pods."""
        logger.info("Testing K8s Query - List Pods")

        response = requests.post(
            f"{base_url}/query",
            json={"uri": "/api/v1/namespaces/default/pods"},
            headers=encrypted_auth_headers,
            timeout=TIMEOUT,
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "data" in data
        # Handle both dict and list response formats
        items = data["data"].get("items", []) if isinstance(data["data"], dict) else data["data"]
        logger.info(f"Successfully queried pods: {len(items)} found")

    def test_get_pod_logs(self, base_url: str, encrypted_auth_headers: dict[str, str]) -> None:
        """Test fetching pod logs from first available pod in any namespace."""
        logger.info("Testing K8s Pod Logs")

        # First, get list of all namespaces
        namespaces_response = requests.post(
            f"{base_url}/query",
            json={"uri": "/api/v1/namespaces"},
            headers=encrypted_auth_headers,
            timeout=TIMEOUT,
        )

        assert namespaces_response.status_code == HTTPStatus.OK
        namespaces_data = namespaces_response.json()
        ns_items = (
            namespaces_data["data"].get("items", [])
            if isinstance(namespaces_data.get("data"), dict)
            else namespaces_data.get("data", [])
        )

        if not ns_items:
            pytest.skip("No namespaces found in the cluster")

        # Try to find pods in each namespace until we find one
        pod_name = None
        pod_namespace = None

        for ns in ns_items:
            namespace = ns["metadata"]["name"]
            pods_response = requests.post(
                f"{base_url}/query",
                json={"uri": f"/api/v1/namespaces/{namespace}/pods"},
                headers=encrypted_auth_headers,
                timeout=TIMEOUT,
            )

            if pods_response.status_code == HTTPStatus.OK:
                pods_data = pods_response.json()
                data = pods_data.get("data", {})
                items = data.get("items", []) if isinstance(data, dict) else data

                if items:
                    pod_name = items[0]["metadata"]["name"]
                    pod_namespace = namespace
                    logger.info(f"Found pod: {pod_name} in namespace: {pod_namespace}")
                    break

        if not pod_name:
            pytest.skip("No pods found in any namespace")

        # Fetch logs
        logs_response = requests.post(
            f"{base_url}/pods/logs",
            json={
                "name": pod_name,
                "namespace": pod_namespace,
                "tail_lines": 10,
            },
            headers=encrypted_auth_headers,
            timeout=TIMEOUT,
        )

        # Accept both 200 (logs available) and 404 (no logs/diagnostic info) as valid responses
        assert logs_response.status_code in (HTTPStatus.OK, HTTPStatus.NOT_FOUND)

        if logs_response.status_code == HTTPStatus.OK:
            # When logs are available, validate the response structure
            logs_data = logs_response.json()
            assert "logs" in logs_data
            assert isinstance(logs_data["logs"], dict)
            assert "current_container" in logs_data["logs"]
            assert "previously_terminated_container" in logs_data["logs"]
            assert "pod_name" in logs_data
            assert logs_data["pod_name"] == pod_name
            logger.info(f"Successfully retrieved logs for pod {pod_name}")
        else:
            # When no logs are available (404), validate error response
            error_data = logs_response.json()
            assert "error" in error_data
            assert error_data["error"] == "Not Found"
            logger.info(f"Pod {pod_name} has no logs or diagnostic information available (404)")
        logger.info(f"Successfully fetched logs from {pod_namespace}/{pod_name}")

    def test_get_cluster_overview(self, base_url: str, encrypted_auth_headers: dict[str, str]) -> None:
        """Test getting cluster-level overview."""
        logger.info("Testing K8s Overview - Cluster Level")

        response = requests.post(
            f"{base_url}/overview",
            json={"namespace": "", "resource_kind": "cluster"},
            headers=encrypted_auth_headers,
            timeout=TIMEOUT,
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "context" in data
        assert len(data["context"]) > 0
        logger.info("Successfully retrieved cluster overview")

    def test_get_namespace_overview(self, base_url: str, encrypted_auth_headers: dict[str, str]) -> None:
        """Test getting namespace-level overview."""
        logger.info("Testing K8s Overview - Namespace Level")

        response = requests.post(
            f"{base_url}/overview",
            json={"namespace": "default", "resource_kind": "namespace"},
            headers=encrypted_auth_headers,
            timeout=TIMEOUT,
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "context" in data
        logger.info(f"Successfully retrieved namespace overview (length: {len(data['context'])})")


class TestKymaToolsAPI:
    """Test suite for Kyma Tools API endpoints."""

    @pytest.fixture(scope="class")
    def base_url(self, base_api_url: str) -> str:
        """Get base URL for Kyma Tools API requests."""
        return f"{base_api_url}/api/tools/kyma"

    def test_query_kyma_functions(self, base_url: str, encrypted_auth_headers: dict[str, str]) -> None:
        """Test querying Kyma serverless functions."""
        logger.info("Testing Kyma Query - List Functions")

        response = requests.post(
            f"{base_url}/query",
            json={"uri": "/apis/serverless.kyma-project.io/v1alpha2/functions"},
            headers=encrypted_auth_headers,
            timeout=TIMEOUT,
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "data" in data
        # Handle both dict and list response formats
        items = data["data"].get("items", []) if isinstance(data["data"], dict) else data["data"]
        logger.info(f"Successfully queried functions: {len(items)} found")

    def test_query_kyma_apirules(self, base_url: str, encrypted_auth_headers: dict[str, str]) -> None:
        """Test querying Kyma API Rules."""
        logger.info("Testing Kyma Query - List APIRules")

        response = requests.post(
            f"{base_url}/query",
            json={"uri": "/apis/gateway.kyma-project.io/v1beta1/apirules"},
            headers=encrypted_auth_headers,
            timeout=TIMEOUT,
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "data" in data
        # Handle both dict and list response formats
        items = data["data"].get("items", []) if isinstance(data["data"], dict) else data["data"]
        logger.info(f"Successfully queried APIRules: {len(items)} found")

    @pytest.mark.parametrize(
        "resource_kind,expected_api_version",
        [
            ("Function", "serverless.kyma-project.io/v1alpha2"),
            ("APIRule", "gateway.kyma-project.io/v1beta1"),
            ("Subscription", "eventing.kyma-project.io/v1alpha2"),
        ],
    )
    def test_get_resource_version(
        self,
        base_url: str,
        encrypted_auth_headers: dict[str, str],
        resource_kind: str,
        expected_api_version: str,
    ) -> None:
        """Test getting API version for various Kyma resource kinds."""
        logger.info(f"Testing Kyma Resource Version - {resource_kind}")

        response = requests.post(
            f"{base_url}/resource-version",
            json={"resource_kind": resource_kind},
            headers=encrypted_auth_headers,
            timeout=TIMEOUT,
        )

        # Skip if resource CRD is not installed in the cluster
        if response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR:
            pytest.skip(f"Resource {resource_kind} CRD not installed in cluster")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "resource_kind" in data
        assert "api_version" in data
        assert data["resource_kind"] == resource_kind
        assert data["api_version"] == expected_api_version
        logger.info(f"Successfully verified {resource_kind} -> {expected_api_version}")

    @pytest.mark.parametrize(
        "query",
        [
            "Help me get started with kyma",
            "How to create a function in Kyma?",
            "What is an APIRule?",
            "How to troubleshoot Kyma Istio module?",
        ],
    )
    def test_search_kyma_documentation(self, base_url: str, query: str) -> None:
        """Test searching Kyma documentation (no auth required)."""
        logger.info(f"Testing Kyma Documentation Search: '{query}'")

        response = requests.post(
            f"{base_url}/search",
            json={"query": query},
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT,
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "results" in data
        assert "query" in data
        assert data["query"] == query
        assert len(data["results"]) > 0
        logger.info(f"Successfully searched documentation: {len(data['results'])} documents returned")

    @pytest.mark.parametrize(
        "top_k,query",
        [
            (None, "Help me get started with kyma"),  # Test default top_k
            (1, "Help me get started with kyma"),
            (3, "What is an APIRule?"),
            (5, "How to troubleshoot Kyma?"),
            (10, "Kyma serverless functions"),
        ],
    )
    def test_search_with_top_k_parameter(self, base_url: str, top_k: int | None, query: str) -> None:
        """Test searching Kyma documentation with custom and default top_k parameter."""
        if top_k is None:
            logger.info(f"Testing Kyma Documentation Search with default top_k: '{query}'")
            request_json = {"query": query}
            expected_max = 5  # Default value
        else:
            logger.info(f"Testing Kyma Documentation Search with top_k={top_k}: '{query}'")
            request_json = {"query": query, "top_k": top_k}
            expected_max = top_k

        response = requests.post(
            f"{base_url}/search",
            json=request_json,
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT,
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "results" in data
        assert "query" in data
        assert data["query"] == query
        assert isinstance(data["results"], list)
        # Verify we get at most expected_max documents (may be less if fewer available)
        assert len(data["results"]) <= expected_max
        logger.info(
            f"Successfully searched documentation with top_k={top_k or 'default'}: "
            f"{len(data['results'])} documents returned"
        )


class TestToolsAPIErrorHandling:
    """Test suite for Tools API error handling."""

    def test_query_missing_uri_returns_422(self, base_api_url: str, encrypted_auth_headers: dict[str, str]) -> None:
        """Test that missing required field returns 422."""
        response = requests.post(
            f"{base_api_url}/api/tools/k8s/query",
            json={},  # Missing 'uri' field
            headers=encrypted_auth_headers,
            timeout=TIMEOUT,
        )

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    def test_query_without_auth_returns_error(self, base_api_url: str) -> None:
        """Test that query without auth headers returns error."""
        response = requests.post(
            f"{base_api_url}/api/tools/k8s/query",
            json={"uri": "/api/v1/pods"},
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT,
        )

        # Should return error (either 422 or 500 depending on validation)
        assert response.status_code >= MIN_ERROR_STATUS_CODE

    def test_search_missing_query_returns_422(self, base_api_url: str) -> None:
        """Test that search without query returns 422."""
        response = requests.post(
            f"{base_api_url}/api/tools/kyma/search",
            json={},  # Missing 'query' field
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT,
        )

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    def test_invalid_resource_kind_returns_error(
        self, base_api_url: str, encrypted_auth_headers: dict[str, str]
    ) -> None:
        """Test that invalid resource kind returns error."""
        response = requests.post(
            f"{base_api_url}/api/tools/kyma/resource-version",
            json={"resource_kind": "InvalidResourceKind"},
            headers=encrypted_auth_headers,
            timeout=TIMEOUT,
        )

        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
