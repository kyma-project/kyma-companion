"""
Unit tests for K8s Tools API Router.

This module tests the K8s tools REST API endpoints defined in
src/routers/k8s_tools_api.py, focusing on business logic and error handling.
"""

from http import HTTPStatus

import pytest
from conftest import get_sample_headers


class TestQueryEndpoint:
    """Test cases for K8s resource query endpoint."""

    @pytest.mark.parametrize(
        "uri, expected_status",
        [
            ("/api/v1/pods", HTTPStatus.OK),
            ("/api/v1/namespaces/default/pods", HTTPStatus.OK),
            ("/apis/apps/v1/deployments", HTTPStatus.OK),
        ],
    )
    def test_query_with_valid_uri(self, k8s_client_factory, uri, expected_status):
        """Test query endpoint with various valid URIs."""
        client = k8s_client_factory()
        headers = get_sample_headers()

        response = client.post(
            "/api/tools/k8s/query",
            json={"uri": uri},
            headers=headers,
        )

        assert response.status_code == expected_status
        assert "data" in response.json()

    def test_query_handles_k8s_client_error(self, k8s_client_factory):
        """Test that query endpoint handles K8s client errors."""
        client = k8s_client_factory(should_fail=True)
        headers = get_sample_headers()

        response = client.post(
            "/api/tools/k8s/query",
            json={"uri": "/api/v1/pods"},
            headers=headers,
        )

        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


class TestLogsEndpoint:
    """Test cases for K8s pod logs endpoint."""

    def test_logs_with_valid_request(self, k8s_client_factory):
        """Test fetching logs with valid pod information."""
        client = k8s_client_factory()
        headers = get_sample_headers()
        request_body = {
            "name": "test-pod",
            "namespace": "default",
            "tail_lines": 10,
        }

        response = client.post(
            "/api/tools/k8s/pods/logs",
            json=request_body,
            headers=headers,
        )

        assert response.status_code == HTTPStatus.OK
        response_data = response.json()
        assert "logs" in response_data
        assert isinstance(response_data["logs"], dict)
        assert "current_container" in response_data["logs"]
        assert "previously_terminated_container" in response_data["logs"]

    def test_logs_with_container_name(self, k8s_client_factory):
        """Test fetching logs with specific container name."""
        client = k8s_client_factory()
        headers = get_sample_headers()
        request_body = {
            "name": "test-pod",
            "namespace": "default",
            "container_name": "main-container",
            "tail_lines": 50,
        }

        response = client.post(
            "/api/tools/k8s/pods/logs",
            json=request_body,
            headers=headers,
        )

        assert response.status_code == HTTPStatus.OK

    def test_logs_handles_fetch_error(self, k8s_client_factory):
        """Test that logs endpoint handles fetch errors gracefully."""
        client = k8s_client_factory(should_fail=True)
        headers = get_sample_headers()
        request_body = {
            "name": "non-existent-pod",
            "namespace": "default",
        }

        response = client.post(
            "/api/tools/k8s/pods/logs",
            json=request_body,
            headers=headers,
        )

        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR

    @pytest.mark.parametrize(
        "auth_error_status",
        [HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN],
    )
    def test_logs_raises_auth_errors_immediately(self, k8s_client_factory, auth_error_status):
        """Test that authentication/authorization errors (401/403) are returned with correct status."""
        client = k8s_client_factory(should_fail=True, fail_with_status=auth_error_status)
        headers = get_sample_headers()
        request_body = {
            "name": "test-pod",
            "namespace": "default",
        }

        response = client.post(
            "/api/tools/k8s/pods/logs",
            json=request_body,
            headers=headers,
        )

        # Auth errors should be returned with their original status code
        assert response.status_code == auth_error_status

    def test_logs_returns_404_when_no_data_available(self, k8s_client_factory):
        """Test that 404 is returned when no logs and no diagnostic info available."""
        client = k8s_client_factory(logs_scenario="no_logs_no_diagnostic")
        headers = get_sample_headers()
        request_body = {
            "name": "test-pod",
            "namespace": "default",
            "container_name": "main",
        }

        response = client.post(
            "/api/tools/k8s/pods/logs",
            json=request_body,
            headers=headers,
        )

        assert response.status_code == HTTPStatus.NOT_FOUND
        response_data = response.json()
        assert "error" in response_data
        assert response_data["error"] == "Not Found"
        assert "message" in response_data

    def test_logs_returns_200_when_no_logs_but_has_diagnostic(self, k8s_client_factory):
        """Test that 200 is returned when no logs but diagnostic info is available."""
        client = k8s_client_factory(logs_scenario="no_logs_with_diagnostic")
        headers = get_sample_headers()
        request_body = {
            "name": "test-pod",
            "namespace": "default",
            "container_name": "main",
        }

        response = client.post(
            "/api/tools/k8s/pods/logs",
            json=request_body,
            headers=headers,
        )

        assert response.status_code == HTTPStatus.OK
        response_data = response.json()
        assert "logs" in response_data
        assert "diagnostic_context" in response_data
        assert response_data["diagnostic_context"] is not None
        # Verify diagnostic context has useful information
        assert "Failed to pull image" in response_data["diagnostic_context"]["events"]
        assert "container_statuses" in response_data["diagnostic_context"]

    def test_logs_returns_200_when_only_previous_logs_available(self, k8s_client_factory):
        """Test that 200 is returned when only previous logs are available."""
        client = k8s_client_factory(logs_scenario="previous_logs_only")
        headers = get_sample_headers()
        request_body = {
            "name": "test-pod",
            "namespace": "default",
            "container_name": "main",
        }

        response = client.post(
            "/api/tools/k8s/pods/logs",
            json=request_body,
            headers=headers,
        )

        assert response.status_code == HTTPStatus.OK
        response_data = response.json()
        assert "logs" in response_data
        # Current logs should indicate unavailability
        assert "Logs not available" in response_data["logs"]["current_container"]
        # Previous logs should contain actual log content
        assert "Previous log line 1" in response_data["logs"]["previously_terminated_container"]

    def test_logs_returns_400_for_invalid_container(self, k8s_client_factory):
        """Test that 400 is returned with diagnostic context for invalid container name."""
        client = k8s_client_factory(logs_scenario="invalid_container")
        headers = get_sample_headers()
        request_body = {
            "name": "test-pod",
            "namespace": "default",
            "container_name": "_nginx",
        }

        response = client.post(
            "/api/tools/k8s/pods/logs",
            json=request_body,
            headers=headers,
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        response_data = response.json()
        # Should have normal response structure
        assert "logs" in response_data
        assert "diagnostic_context" in response_data
        # Error message should be in current_container
        assert "not valid for pod" in response_data["logs"]["current_container"]
        # Diagnostic context should show valid containers
        assert response_data["diagnostic_context"] is not None
        assert "container_statuses" in response_data["diagnostic_context"]


class TestOverviewEndpoint:
    """Test cases for K8s cluster overview endpoint."""

    @pytest.mark.parametrize(
        "namespace, resource_kind",
        [
            ("", "cluster"),
            ("default", "namespace"),
            ("kube-system", "namespace"),
        ],
    )
    def test_overview_with_valid_params(self, k8s_client_factory, namespace, resource_kind):
        """Test overview endpoint with various valid parameters."""
        client = k8s_client_factory()
        headers = get_sample_headers()
        request_body = {
            "namespace": namespace,
            "resource_kind": resource_kind,
        }

        response = client.post(
            "/api/tools/k8s/overview",
            json=request_body,
            headers=headers,
        )

        assert response.status_code == HTTPStatus.OK
        response_data = response.json()
        assert "context" in response_data


class TestErrorHandling:
    """Test cases for error handling scenarios."""

    def test_invalid_json_body_returns_422(self, k8s_client_factory):
        """Test that invalid JSON body returns validation error."""
        client = k8s_client_factory()
        headers = get_sample_headers()

        response = client.post(
            "/api/tools/k8s/query",
            content="invalid json",
            headers=headers,
        )

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
        # Verify response is valid JSON with expected structure
        data = response.json()
        assert "error" in data
        assert "message" in data
        assert "detail" in data
        assert data["error"] == "Validation Error"
        # Verify error details are serializable (no bytes)
        assert isinstance(data["detail"], list)

    def test_missing_required_field_returns_422(self, k8s_client_factory):
        """Test that missing required field returns validation error."""
        client = k8s_client_factory()
        headers = get_sample_headers()

        response = client.post(
            "/api/tools/k8s/query",
            json={},  # Missing 'uri' field
            headers=headers,
        )

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
