"""
Evaluation tests for K8s and Kyma Tools API endpoints.

These tests validate the Tools API endpoints by making actual HTTP requests
to a running Kyma Companion server instance and verifying the responses against
a real Kubernetes cluster.
"""

import logging
from http import HTTPStatus

import pytest
import requests
from common.config import Config

logger = logging.getLogger(__name__)

# Minimum status code for client/server errors
MIN_ERROR_STATUS_CODE = 400
TIMEOUT = 120  # seconds


# Shared fixtures for all test classes
@pytest.fixture(scope="module")
def config() -> Config:
    """Load configuration for tests."""
    return Config()


@pytest.fixture(scope="module")
def auth_headers(config: Config) -> dict[str, str]:
    """Get authentication headers for API requests."""
    return {
        "Content-Type": "application/json",
        "x-cluster-url": config.test_cluster_url,
        "x-cluster-certificate-authority-data": config.test_cluster_ca_data,
        "x-k8s-authorization": config.test_cluster_auth_token,
    }


@pytest.fixture(scope="module")
def base_api_url(config: Config) -> str:
    """Get base API URL."""
    return config.companion_api_url


class TestK8sToolsAPI:
    """Test suite for K8s Tools API endpoints."""

    @pytest.fixture(scope="class")
    def base_url(self, base_api_url: str) -> str:
        """Get base URL for K8s Tools API requests."""
        return f"{base_api_url}/api/tools/k8s"

    def test_query_k8s_deployments(
        self, base_url: str, auth_headers: dict[str, str]
    ) -> None:
        """Test querying K8s deployments in default namespace."""
        logger.info("Testing K8s Query - List Deployments")

        response = requests.post(
            f"{base_url}/query",
            json={"uri": "/apis/apps/v1/namespaces/default/deployments"},
            headers=auth_headers,
            timeout=TIMEOUT,
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "data" in data
        # Handle both dict and list response formats
        items = (
            data["data"].get("items", [])
            if isinstance(data["data"], dict)
            else data["data"]
        )
        logger.info(f"Successfully queried deployments: {len(items)} found")

    def test_query_k8s_pods(self, base_url: str, auth_headers: dict[str, str]) -> None:
        """Test querying K8s pods."""
        logger.info("Testing K8s Query - List Pods")

        response = requests.post(
            f"{base_url}/query",
            json={"uri": "/api/v1/namespaces/default/pods"},
            headers=auth_headers,
            timeout=TIMEOUT,
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "data" in data
        # Handle both dict and list response formats
        items = (
            data["data"].get("items", [])
            if isinstance(data["data"], dict)
            else data["data"]
        )
        logger.info(f"Successfully queried pods: {len(items)} found")

    def test_get_pod_logs(self, base_url: str, auth_headers: dict[str, str]) -> None:
        """Test fetching pod logs from first available pod in any namespace."""
        logger.info("Testing K8s Pod Logs")

        # First, get list of all namespaces
        namespaces_response = requests.post(
            f"{base_url}/query",
            json={"uri": "/api/v1/namespaces"},
            headers=auth_headers,
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
                headers=auth_headers,
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
            headers=auth_headers,
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
            logger.info(
                f"Pod {pod_name} has no logs or diagnostic information available (404)"
            )
        logger.info(f"Successfully fetched logs from {pod_namespace}/{pod_name}")

    def test_get_cluster_overview(
        self, base_url: str, auth_headers: dict[str, str]
    ) -> None:
        """Test getting cluster-level overview."""
        logger.info("Testing K8s Overview - Cluster Level")

        response = requests.post(
            f"{base_url}/overview",
            json={"namespace": "", "resource_kind": "cluster"},
            headers=auth_headers,
            timeout=TIMEOUT,
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "context" in data
        assert len(data["context"]) > 0
        logger.info("Successfully retrieved cluster overview")

    def test_get_namespace_overview(
        self, base_url: str, auth_headers: dict[str, str]
    ) -> None:
        """Test getting namespace-level overview."""
        logger.info("Testing K8s Overview - Namespace Level")

        response = requests.post(
            f"{base_url}/overview",
            json={"namespace": "default", "resource_kind": "namespace"},
            headers=auth_headers,
            timeout=TIMEOUT,
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "context" in data
        logger.info(
            f"Successfully retrieved namespace overview (length: {len(data['context'])})"
        )


class TestKymaToolsAPI:
    """Test suite for Kyma Tools API endpoints."""

    @pytest.fixture(scope="class")
    def base_url(self, base_api_url: str) -> str:
        """Get base URL for Kyma Tools API requests."""
        return f"{base_api_url}/api/tools/kyma"

    def test_query_kyma_functions(
        self, base_url: str, auth_headers: dict[str, str]
    ) -> None:
        """Test querying Kyma serverless functions."""
        logger.info("Testing Kyma Query - List Functions")

        response = requests.post(
            f"{base_url}/query",
            json={"uri": "/apis/serverless.kyma-project.io/v1alpha2/functions"},
            headers=auth_headers,
            timeout=TIMEOUT,
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "data" in data
        # Handle both dict and list response formats
        items = (
            data["data"].get("items", [])
            if isinstance(data["data"], dict)
            else data["data"]
        )
        logger.info(f"Successfully queried functions: {len(items)} found")

    def test_query_kyma_apirules(
        self, base_url: str, auth_headers: dict[str, str]
    ) -> None:
        """Test querying Kyma API Rules."""
        logger.info("Testing Kyma Query - List APIRules")

        response = requests.post(
            f"{base_url}/query",
            json={"uri": "/apis/gateway.kyma-project.io/v1beta1/apirules"},
            headers=auth_headers,
            timeout=TIMEOUT,
        )

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "data" in data
        # Handle both dict and list response formats
        items = (
            data["data"].get("items", [])
            if isinstance(data["data"], dict)
            else data["data"]
        )
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
        auth_headers: dict[str, str],
        resource_kind: str,
        expected_api_version: str,
    ) -> None:
        """Test getting API version for various Kyma resource kinds."""
        logger.info(f"Testing Kyma Resource Version - {resource_kind}")

        response = requests.post(
            f"{base_url}/resource-version",
            json={"resource_kind": resource_kind},
            headers=auth_headers,
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
            "How to install Kyma?",
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
        logger.info(
            f"Successfully searched documentation: {len(data['results'])} documents returned"
        )

    @pytest.mark.parametrize(
        "top_k,query",
        [
            (None, "How to install Kyma?"),  # Test default top_k
            (1, "How to install Kyma?"),
            (3, "What is an APIRule?"),
            (5, "How to troubleshoot Kyma?"),
            (10, "Kyma serverless functions"),
        ],
    )
    def test_search_with_top_k_parameter(
        self, base_url: str, top_k: int | None, query: str
    ) -> None:
        """Test searching Kyma documentation with custom and default top_k parameter."""
        if top_k is None:
            logger.info(
                f"Testing Kyma Documentation Search with default top_k: '{query}'"
            )
            request_json = {"query": query}
            expected_max = 5  # Default value
        else:
            logger.info(
                f"Testing Kyma Documentation Search with top_k={top_k}: '{query}'"
            )
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

    def test_query_missing_uri_returns_422(
        self, base_api_url: str, auth_headers: dict[str, str]
    ) -> None:
        """Test that missing required field returns 422."""
        response = requests.post(
            f"{base_api_url}/api/tools/k8s/query",
            json={},  # Missing 'uri' field
            headers=auth_headers,
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
        self, base_api_url: str, auth_headers: dict[str, str]
    ) -> None:
        """Test that invalid resource kind returns error."""
        response = requests.post(
            f"{base_api_url}/api/tools/kyma/resource-version",
            json={"resource_kind": "InvalidResourceKind"},
            headers=auth_headers,
            timeout=TIMEOUT,
        )

        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
