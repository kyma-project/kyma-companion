"""
Unit tests for Cluster Region API Router.
"""

from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from main import app
from routers.common import ClusterRegionResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_response(**kwargs) -> ClusterRegionResponse:
    defaults = {
        "shoot-id": "test-shoot",
        "region": "us-east-1",
        "platformRegion": "cf-us10",
        "provider": "AWS",
        "isEUAccessOnly": False,
    }
    defaults.update(kwargs)
    return ClusterRegionResponse(**defaults)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def test_client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Tests: successful responses
# ---------------------------------------------------------------------------


class TestClusterRegionEndpoint:
    @patch("routers.cluster_region_api.get_cluster_region", new_callable=AsyncMock)
    def test_returns_region_info(self, mock_get, test_client):
        mock_get.return_value = _make_response()

        response = test_client.get("/api/tools/cluster-region/test-shoot")

        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert body["shoot-id"] == "test-shoot"
        assert body["region"] == "us-east-1"
        assert body["platformRegion"] == "cf-us10"
        assert body["provider"] == "AWS"
        assert body["isEUAccessOnly"] is False

    @pytest.mark.parametrize(
        "platform_region, expected",
        [
            ("cf-eu11", True),
            ("cf-ch20", True),
            ("cf-eu01", True),
            ("cf-eu02", True),
            ("cf-eu31", True),
            ("cf-us10", False),
            ("cf-ap10", False),
        ],
    )
    @patch("routers.cluster_region_api.get_cluster_region", new_callable=AsyncMock)
    def test_eu_access_flag(self, mock_get, platform_region, expected, test_client):
        mock_get.return_value = _make_response(platformRegion=platform_region, isEUAccessOnly=expected)

        response = test_client.get("/api/tools/cluster-region/test-shoot")

        assert response.status_code == HTTPStatus.OK
        assert response.json()["isEUAccessOnly"] is expected

    @patch("routers.cluster_region_api.get_cluster_region", new_callable=AsyncMock)
    def test_shoot_id_passed_to_service(self, mock_get, test_client):
        mock_get.return_value = _make_response(**{"shoot-id": "my-shoot-123"})

        test_client.get("/api/tools/cluster-region/my-shoot-123")

        mock_get.assert_awaited_once_with("my-shoot-123")


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------


class TestClusterRegionErrorHandling:
    @patch("routers.cluster_region_api.get_cluster_region", new_callable=AsyncMock)
    def test_not_found(self, mock_get, test_client):
        mock_get.side_effect = HTTPException(
            status_code=HTTPStatus.NOT_FOUND,
            detail="Runtime CR not found for shoot-id 'missing-shoot'",
        )

        response = test_client.get("/api/tools/cluster-region/missing-shoot")

        assert response.status_code == HTTPStatus.NOT_FOUND

    @patch("routers.cluster_region_api.get_cluster_region", new_callable=AsyncMock)
    def test_service_raises_unexpected_error(self, mock_get, test_client):
        mock_get.side_effect = RuntimeError("something exploded")

        response = test_client.get("/api/tools/cluster-region/test-shoot")

        assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


# ---------------------------------------------------------------------------
# Tests: service layer (unit)
# ---------------------------------------------------------------------------


class TestGetClusterRegionService:
    """Test services/cluster_region.py logic directly."""

    @pytest.mark.asyncio
    @patch("services.cluster_region._get_dynamic_client")
    @patch("services.cluster_region.get_redis")
    async def test_returns_cached_value(self, mock_get_redis, mock_dyn_client):
        cached_json = ClusterRegionResponse(
            **{
                "shoot-id": "cached-shoot",
                "region": "eu-central-1",
                "platformRegion": "cf-eu11",
                "provider": "AWS",
                "isEUAccessOnly": True,
            }
        ).model_dump_json(by_alias=True)

        mock_redis_instance = MagicMock()
        mock_redis_instance.has_connection.return_value = True
        mock_redis_instance.get_connection.return_value.get = AsyncMock(return_value=cached_json)
        mock_get_redis.return_value = mock_redis_instance

        from services.cluster_region import get_cluster_region

        result = await get_cluster_region("cached-shoot")

        assert result.shoot_id == "cached-shoot"
        assert result.region == "eu-central-1"
        assert result.is_eu_access_only is True
        mock_dyn_client.assert_not_called()

    @pytest.mark.asyncio
    @patch("services.cluster_region._get_dynamic_client")
    @patch("services.cluster_region.get_redis")
    async def test_fetches_from_kcp_on_cache_miss(self, mock_get_redis, mock_dyn_client):
        mock_redis_instance = MagicMock()
        mock_redis_instance.has_connection.return_value = True
        mock_conn = MagicMock()
        mock_conn.get = AsyncMock(return_value=None)
        mock_conn.setex = AsyncMock()
        mock_redis_instance.get_connection.return_value = mock_conn
        mock_get_redis.return_value = mock_redis_instance

        runtime_item = MagicMock()
        runtime_item.get.side_effect = lambda key, default=None: {
            "metadata": {
                "labels": {
                    "kyma-project.io/shoot-name": "fresh-shoot",
                    "kyma-project.io/region": "us-east-1",
                    "kyma-project.io/platform-region": "cf-us10",
                    "kyma-project.io/provider": "AWS",
                }
            }
        }.get(key, default)

        mock_resource_api = MagicMock()
        mock_resource_api.get.return_value = MagicMock(items=[runtime_item])

        mock_client = MagicMock()
        mock_client.resources.get.return_value = mock_resource_api
        mock_dyn_client.return_value = mock_client

        from services.cluster_region import get_cluster_region

        result = await get_cluster_region("fresh-shoot")

        assert result.region == "us-east-1"
        assert result.platform_region == "cf-us10"
        assert result.provider == "AWS"
        assert result.is_eu_access_only is False
        mock_conn.setex.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("services.cluster_region._get_dynamic_client")
    @patch("services.cluster_region.get_redis")
    async def test_raises_404_when_no_runtime_cr(self, mock_get_redis, mock_dyn_client):
        mock_redis_instance = MagicMock()
        mock_redis_instance.has_connection.return_value = False
        mock_get_redis.return_value = mock_redis_instance

        mock_resource_api = MagicMock()
        mock_resource_api.get.return_value = MagicMock(items=[])
        mock_client = MagicMock()
        mock_client.resources.get.return_value = mock_resource_api
        mock_dyn_client.return_value = mock_client

        from fastapi import HTTPException as FastAPIHTTPException

        from services.cluster_region import get_cluster_region

        with pytest.raises(FastAPIHTTPException) as exc_info:
            await get_cluster_region("ghost-shoot")

        assert exc_info.value.status_code == HTTPStatus.NOT_FOUND

    @pytest.mark.parametrize(
        "platform_region, expected",
        [
            ("cf-eu11", True),
            ("cf-ch20", True),
            ("cf-eu01", True),
            ("cf-eu02", True),
            ("cf-eu31", True),
            ("cf-us10", False),
            ("", False),
        ],
    )
    def test_eu_access_only_logic(self, platform_region, expected):
        from services.cluster_region import _LABEL_PLATFORM_REGION, _build_response

        labels = {_LABEL_PLATFORM_REGION: platform_region}
        result = _build_response("s1", labels)
        assert result.is_eu_access_only is expected
