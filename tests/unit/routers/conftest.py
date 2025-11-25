"""
Shared fixtures for router unit tests.
"""

import pytest
from fastapi.testclient import TestClient

from main import app
from routers.k8s_tools_api import init_k8s_client as init_k8s_client_k8s
from routers.kyma_tools_api import init_k8s_client as init_k8s_client_kyma
from services.k8s import IK8sClient

# Sample test data
SAMPLE_BEARER_TOKEN = "test-token-123"
SAMPLE_CLUSTER_URL = "https://api.test-cluster.example.com"
SAMPLE_CA_DATA = "LS0tLS1CRUdJTi1DRVJUSUZJQ0FURS0tLS0tCg=="


def get_sample_headers() -> dict[str, str]:
    """Get sample HTTP headers for testing."""
    return {
        "x-cluster-url": SAMPLE_CLUSTER_URL,
        "x-cluster-certificate-authority-data": SAMPLE_CA_DATA,
        "x-k8s-authorization": SAMPLE_BEARER_TOKEN,
    }


class MockK8sClient(IK8sClient):
    """Mock implementation of K8s client for testing."""

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self._resource_versions = {
            "Function": "serverless.kyma-project.io/v1alpha2",
            "APIRule": "gateway.kyma-project.io/v1beta1",
            "Subscription": "eventing.kyma-project.io/v1alpha2",
            "TracePipeline": "telemetry.kyma-project.io/v1alpha1",
            "ServiceInstance": "services.cloud.sap.com/v1",
        }

    def get_api_server(self) -> str:
        return SAMPLE_CLUSTER_URL

    async def execute_get_api_request(self, uri: str) -> dict | list[dict]:
        if self.should_fail:
            raise Exception("K8s API request failed")
        if "pods" in uri:
            return {
                "items": [
                    {
                        "metadata": {
                            "name": "test-pod",
                            "namespace": "default",
                        },
                        "status": {"phase": "Running"},
                    }
                ]
            }
        return {"items": [{"metadata": {"name": "test-resource"}}]}

    async def fetch_pod_logs(
        self,
        name: str,
        namespace: str,
        container_name: str = "",
        is_terminated: bool = False,
        tail_limit: int = 100,
    ) -> list[str]:
        if self.should_fail:
            raise Exception("Failed to fetch logs")
        return ["Log line 1", "Log line 2", "Log line 3"]

    def list_not_running_pods(self, namespace: str) -> list[dict]:
        return []

    async def list_nodes_metrics(self) -> list[dict]:
        return []

    def list_k8s_warning_events(self, namespace: str) -> list[dict]:
        return []

    def get_resource_version(self, kind: str) -> str:
        if self.should_fail:
            raise ValueError(f"Resource kind '{kind}' not found")
        if kind in self._resource_versions:
            return self._resource_versions[kind]
        raise ValueError(f"Resource kind '{kind}' not found")


@pytest.fixture(scope="function")
def k8s_client_factory():
    """
    Factory fixture to create k8s test clients with different mock K8s
    client configurations.

    This fixture is used by tests that need to simulate K8s
    cluster interactions with different behaviors (e.g., success, failure).
    """

    def _create_client(should_fail: bool = False):
        mock_k8s_client = MockK8sClient(should_fail=should_fail)

        def get_mock_k8s_client():
            return mock_k8s_client

        # Override for both K8s and Kyma routers
        app.dependency_overrides[init_k8s_client_k8s] = get_mock_k8s_client
        app.dependency_overrides[init_k8s_client_kyma] = get_mock_k8s_client
        test_client = TestClient(app)
        return test_client

    yield _create_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def test_client():
    """
    Simple test client fixture without K8s client override.

    This fixture is used by tests that don't need K8s cluster access
    (e.g., search endpoint that only uses models).
    """
    client = TestClient(app)
    yield client
