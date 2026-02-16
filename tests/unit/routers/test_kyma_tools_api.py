"""
Unit tests for Kyma Tools API Router.

This module tests the Kyma tools REST API endpoints defined in
src/routers/kyma_tools_api.py, focusing on business logic and error
handling.
"""

from http import HTTPStatus

import pytest
from conftest import get_sample_headers


class TestQueryEndpoint:
    """Test cases for Kyma resource query endpoint."""

    @pytest.mark.parametrize(
        "uri, expected_status",
        [
            (
                "/apis/serverless.kyma-project.io/v1alpha2/functions",
                HTTPStatus.OK,
            ),
            (
                "/apis/gateway.kyma-project.io/v1beta1/apirules",
                HTTPStatus.OK,
            ),
            (
                "/apis/eventing.kyma-project.io/v1alpha2/subscriptions",
                HTTPStatus.OK,
            ),
        ],
    )
    def test_query_with_valid_uri(self, k8s_client_factory, uri, expected_status):
        """Test query endpoint with various valid Kyma resource URIs."""
        client = k8s_client_factory()
        headers = get_sample_headers()

        response = client.post(
            "/api/tools/kyma/query",
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
            "/api/tools/kyma/query",
            json={"uri": "/apis/serverless.kyma-project.io/v1alpha2/functions"},
            headers=headers,
        )

        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


class TestResourceVersionEndpoint:
    """Test cases for Kyma resource version endpoint."""

    @pytest.mark.parametrize(
        "resource_kind",
        [
            "Function",
            "APIRule",
            "Subscription",
            "TracePipeline",
            "ServiceInstance",
        ],
    )
    def test_resource_version_with_valid_kind(self, k8s_client_factory, resource_kind):
        """Test resource version endpoint with valid Kyma resource kinds."""
        client = k8s_client_factory()
        headers = get_sample_headers()

        response = client.post(
            "/api/tools/kyma/resource-version",
            json={"resource_kind": resource_kind},
            headers=headers,
        )

        assert response.status_code == HTTPStatus.OK
        response_data = response.json()
        assert "resource_kind" in response_data
        assert "api_version" in response_data
        assert response_data["resource_kind"] == resource_kind

    def test_resource_version_handles_lookup_error(self, k8s_client_factory):
        """Test resource version endpoint handles lookup errors."""
        client = k8s_client_factory(should_fail=True)
        headers = get_sample_headers()

        response = client.post(
            "/api/tools/kyma/resource-version",
            json={"resource_kind": "NonExistentKind"},
            headers=headers,
        )

        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


class TestSearchEndpoint:
    """
    Test cases for Kyma docs search endpoint.

    NOTE: Search endpoint does not require K8s cluster access,
    so these tests use test_client instead of k8s_client_factory.
    """

    def test_search_with_valid_query(self, test_client):
        """Test search endpoint with valid query."""
        response = test_client.post(
            "/api/tools/kyma/search",
            json={"query": "How to create a Kyma function?"},
        )

        assert response.status_code == HTTPStatus.OK
        response_data = response.json()
        assert "results" in response_data

    @pytest.mark.parametrize(
        "query",
        [
            "How to create a Kyma function?",
            "What is an APIRule?",
            "How to troubleshoot Kyma Istio module?",
            "Kyma eventing configuration",
        ],
    )
    def test_search_with_various_queries(self, test_client, query):
        """Test search endpoint with various query types."""
        response = test_client.post(
            "/api/tools/kyma/search",
            json={"query": query},
        )

        assert response.status_code == HTTPStatus.OK

    def test_search_without_query_returns_422(self, test_client):
        """Test search endpoint without query returns validation error."""
        response = test_client.post(
            "/api/tools/kyma/search",
            json={},  # Missing 'query' field
        )

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    def test_search_handles_empty_query(self, test_client):
        """Test search endpoint handles empty query gracefully."""
        response = test_client.post(
            "/api/tools/kyma/search",
            json={"query": ""},
        )

        # Empty queries are handled gracefully and return results
        assert response.status_code == HTTPStatus.OK


class TestErrorHandling:
    """Test cases for error handling scenarios."""

    def test_invalid_json_body_returns_422(self, k8s_client_factory):
        """Test that invalid JSON body returns validation error."""
        client = k8s_client_factory()
        headers = get_sample_headers()

        response = client.post(
            "/api/tools/kyma/query",
            content="invalid json",
            headers=headers,
        )

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    def test_missing_required_field_returns_422(self, k8s_client_factory):
        """Test that missing required field returns validation error."""
        client = k8s_client_factory()
        headers = get_sample_headers()

        response = client.post(
            "/api/tools/kyma/query",
            json={},  # Missing 'uri' field
            headers=headers,
        )

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    def test_search_with_whitespace_query(self, test_client):
        """Test search with whitespace-only query string."""
        response = test_client.post(
            "/api/tools/kyma/search",
            json={"query": "   "},  # Whitespace only
        )

        # Should handle gracefully
        assert response.status_code in [
            HTTPStatus.OK,
            HTTPStatus.BAD_REQUEST,
            HTTPStatus.INTERNAL_SERVER_ERROR,
        ]
