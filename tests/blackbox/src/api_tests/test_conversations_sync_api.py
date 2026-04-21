"""
API tests for the synchronous messages endpoint.

These tests validate the POST /api/conversations/{id}/messages/sync endpoint by
making actual HTTP requests to a running Kyma Companion server instance.
"""

import logging
from http import HTTPStatus

import pytest
import requests
from common.config import Config

logger = logging.getLogger(__name__)

TIMEOUT = 300  # seconds; sync endpoint waits for the full response


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


@pytest.fixture(scope="module")
def conversation_id(base_api_url: str, auth_headers: dict[str, str]) -> str:
    """Initialize a conversation and return its ID."""
    response = requests.post(
        f"{base_api_url}/api/conversations",
        json={"resource_kind": "Cluster"},
        headers=auth_headers,
        timeout=TIMEOUT,
    )
    assert response.status_code == HTTPStatus.OK, (
        f"Failed to initialize conversation: {response.status_code} {response.text}"
    )
    data = response.json()
    return data["conversation_id"]


class TestConversationsSyncAPI:
    """Test suite for the synchronous messages endpoint."""

    def test_sync_returns_answer_string(
        self,
        base_api_url: str,
        auth_headers: dict[str, str],
        conversation_id: str,
    ) -> None:
        """Test that the sync endpoint returns a JSON object with a non-empty answer string."""
        logger.info(f"Testing sync messages endpoint for conversation {conversation_id}")

        response = requests.post(
            f"{base_api_url}/api/conversations/{conversation_id}/messages/sync",
            json={"query": "What is Kyma?", "resource_kind": "Cluster"},
            headers=auth_headers,
            timeout=TIMEOUT,
        )

        assert response.status_code == HTTPStatus.OK
        assert response.headers["content-type"].startswith("application/json")
        data = response.json()
        assert "answer" in data
        assert isinstance(data["answer"], str)
        assert len(data["answer"]) > 0
        logger.info(f"Sync endpoint returned answer of length {len(data['answer'])}")

    def test_sync_without_auth_returns_error(
        self,
        base_api_url: str,
        conversation_id: str,
    ) -> None:
        """Test that the sync endpoint returns an error when no auth headers are provided."""
        response = requests.post(
            f"{base_api_url}/api/conversations/{conversation_id}/messages/sync",
            json={"query": "What is Kyma?", "resource_kind": "Cluster"},
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT,
        )

        assert response.status_code >= HTTPStatus.BAD_REQUEST

    def test_sync_with_invalid_conversation_id_returns_422(
        self,
        base_api_url: str,
        auth_headers: dict[str, str],
    ) -> None:
        """Test that an invalid conversation ID returns 422."""
        response = requests.post(
            f"{base_api_url}/api/conversations/not-a-uuid/messages/sync",
            json={"query": "What is Kyma?", "resource_kind": "Cluster"},
            headers=auth_headers,
            timeout=TIMEOUT,
        )

        assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
