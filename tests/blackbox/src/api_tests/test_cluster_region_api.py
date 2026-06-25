"""
API tests for the Cluster Region endpoint.

These tests validate GET /api/tools/cluster-region/{shoot_id} by reading
Runtime CRs installed in the k3d test cluster's kcp-system namespace.

Prerequisites (applied by the CI workflow before this test runs):
  - KIM CRD installed: infrastructuremanager.kyma-project.io_runtimes.yaml
  - kcp-system namespace created
  - Runtime CRs applied from tests/blackbox/data/api-test-crd-config/
"""

import logging
from http import HTTPStatus

import pytest
import requests
from common.config import Config

logger = logging.getLogger(__name__)

TIMEOUT = 30  # seconds


@pytest.fixture(scope="module")
def config() -> Config:
    """Load configuration for tests."""
    return Config()


@pytest.fixture(scope="module")
def base_url(config: Config) -> str:
    """Get base URL for cluster-region requests."""
    return f"{config.companion_api_url}/api/tools/cluster-region"


class TestClusterRegionAPI:
    """Test suite for the Cluster Region API endpoint."""

    def test_general_runtime_returns_region(self, base_url: str) -> None:
        """cr-general.yaml: non-EU runtime returns correct region and provider."""
        shoot_id = "c-a1b2c3d"
        response = requests.get(f"{base_url}/{shoot_id}", timeout=TIMEOUT)

        assert response.status_code == HTTPStatus.OK, response.text
        data = response.json()
        assert data["shoot-id"] == shoot_id
        assert data["region"] == "eu-central-1"
        assert data["platformRegion"] == "cd-eu11"
        assert data["provider"] == "aws"
        assert data["isEUAccessOnly"] is False

    def test_eu_only_runtime_is_eu_access(self, base_url: str) -> None:
        """cr-eu-only.yaml: EU-Access runtime returns isEUAccessOnly=True."""
        shoot_id = "c-b2c3d4e"
        response = requests.get(f"{base_url}/{shoot_id}", timeout=TIMEOUT)

        assert response.status_code == HTTPStatus.OK, response.text
        data = response.json()
        assert data["shoot-id"] == shoot_id
        assert data["region"] == "eu-west-1"
        assert data["platformRegion"] == "cf-eu11"
        assert data["provider"] == "aws"
        assert data["isEUAccessOnly"] is True

    def test_unknown_shoot_id_returns_404(self, base_url: str) -> None:
        """Non-existent shoot-id returns 404 Not Found."""
        response = requests.get(f"{base_url}/c-notexist", timeout=TIMEOUT)

        assert response.status_code == HTTPStatus.NOT_FOUND

    @pytest.mark.parametrize("shoot_id", ["c-a1b2c3d", "c-b2c3d4e"])
    def test_response_schema(self, base_url: str, shoot_id: str) -> None:
        """All required response fields are present and correctly typed."""
        response = requests.get(f"{base_url}/{shoot_id}", timeout=TIMEOUT)

        assert response.status_code == HTTPStatus.OK, response.text
        data = response.json()
        assert isinstance(data.get("shoot-id"), str)
        assert isinstance(data.get("region"), str)
        assert isinstance(data.get("platformRegion"), str)
        assert isinstance(data.get("provider"), str)
        assert isinstance(data.get("isEUAccessOnly"), bool)
