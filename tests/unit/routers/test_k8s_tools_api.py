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
        assert "current_pod" in response_data["logs"]
        assert "previous_pod" in response_data["logs"]

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
