"""
Shared fixtures for router unit tests.
"""

from http import HTTPStatus
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from routers.common import init_models_dict
from routers.k8s_tools_api import init_k8s_client as init_k8s_client_k8s
from routers.kyma_tools_api import init_k8s_client as init_k8s_client_kyma
from services.k8s import IK8sClient
from services.k8s_models import (
    ContainerStatus,
    PodLogs,
    PodLogsDiagnosticContext,
    PodLogsResult,
)
from utils.exceptions import K8sClientError, NoLogsAvailableError

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

    def __init__(
        self,
        should_fail: bool = False,
        fail_with_status: int = HTTPStatus.INTERNAL_SERVER_ERROR,
        logs_scenario: str = "success",
    ):
        self.should_fail = should_fail
        self.fail_with_status = fail_with_status
        self.logs_scenario = logs_scenario
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
            raise K8sClientError(
                message="K8s API request failed",
                status_code=self.fail_with_status,
                uri=uri,
            )
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
        tail_limit: int = 100,
    ) -> PodLogsResult:
        if self.should_fail:
            raise K8sClientError(
                message="Failed to fetch logs",
                status_code=self.fail_with_status,
                uri=f"/api/v1/namespaces/{namespace}/pods/{name}/log",
            )

        # Return different scenarios based on logs_scenario parameter
        if self.logs_scenario == "no_logs_no_diagnostic":
            # No logs and no diagnostic information - raise exception
            raise NoLogsAvailableError(
                message=f"No logs or diagnostic information available for pod '{name}' in namespace '{namespace}'",
                pod=name,
                namespace=namespace,
                container=container_name,
            )
        elif self.logs_scenario == "no_logs_with_diagnostic":
            # No logs but has diagnostic information
            return PodLogsResult(
                logs=PodLogs(
                    current_container="Logs not available. Container is waiting",
                    previously_terminated_container="Not available (container has not been restarted)",
                ),
                diagnostic_context=PodLogsDiagnosticContext(
                    events="LAST SEEN   TYPE      REASON    MESSAGE\n"
                    "2m ago      Warning   Failed    Failed to pull image",
                    container_statuses={
                        "main": ContainerStatus(
                            state="Waiting",
                            reason="ImagePullBackOff",
                            message="Back-off pulling image",
                            restart_count=0,
                        )
                    },
                ),
            )
        elif self.logs_scenario == "previous_logs_only":
            # Only previous logs available
            return PodLogsResult(
                logs=PodLogs(
                    current_container="Logs not available. Container restarted",
                    previously_terminated_container="Previous log line 1\nPrevious log line 2",
                ),
            )
        else:
            # Default success scenario
            return PodLogsResult(
                logs=PodLogs(
                    current_container="Log line 1\nLog line 2\nLog line 3",
                    previously_terminated_container="Not available (container has not been restarted)",
                ),
            )

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

    def _create_client(
        should_fail: bool = False,
        fail_with_status: int = HTTPStatus.INTERNAL_SERVER_ERROR,
        logs_scenario: str = "success",
    ):
        mock_k8s_client = MockK8sClient(
            should_fail=should_fail,
            fail_with_status=fail_with_status,
            logs_scenario=logs_scenario,
        )

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
    Simple test client fixture with mocked models and RAG dependencies.

    This fixture is used by tests that don't need K8s cluster access
    but need models (e.g., search endpoint).
    """
    # Create mock models dictionary
    mock_embedding = Mock()
    mock_model = Mock()

    mock_models = {
        "embedding": mock_embedding,
        "model": mock_model,
    }

    def get_mock_models():
        return mock_models

    # Mock RAGSystem to avoid Hana connection
    with patch("agents.kyma.tools.search.RAGSystem") as mock_rag_class:
        # Create mock RAG instance
        mock_rag_instance = Mock()
        mock_rag_instance.aretrieve = AsyncMock(
            return_value=[
                Mock(page_content="Mock Kyma documentation."),
                Mock(page_content="Another Kyma document."),
            ]
        )
        mock_rag_class.return_value = mock_rag_instance

        # Override the models dependency
        app.dependency_overrides[init_models_dict] = get_mock_models
        client = TestClient(app)
        yield client
