"""Integration tests for probe endpoints with real Hana singleton behavior."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE

from main import app
from routers.probes import ILLMProbe, IRedis, IUsageTrackerProbe
from services.hana import Hana
from services.probes import get_llm_probe, get_usage_tracker_probe
from services.redis import get_redis


class TestProbesIntegration:
    """Integration tests for probes that verify actual Hana singleton behavior."""

    def teardown_method(self):
        """Clean up after each test."""
        app.dependency_overrides = {}
        Hana._reset_for_tests()

    def _setup_healthy_dependencies(self):
        """Set up all non-Hana dependencies as healthy."""
        mock_redis = MagicMock(spec=IRedis)
        mock_redis.is_connection_operational = AsyncMock(return_value=True)
        app.dependency_overrides[get_redis] = lambda: mock_redis

        usage_tracker_probe = MagicMock(spec=IUsageTrackerProbe)
        usage_tracker_probe.is_healthy = MagicMock(return_value=True)
        app.dependency_overrides[get_usage_tracker_probe] = lambda: usage_tracker_probe

        mock_llm_probe = MagicMock(spec=ILLMProbe)
        mock_llm_probe.get_llms_states.return_value = {"model1": True}
        app.dependency_overrides[get_llm_probe] = lambda: mock_llm_probe

    def test_healthz_reflects_mark_unhealthy(self):
        """Test that healthz probe returns 503 when mark_unhealthy() is called."""
        # Given: Create a real Hana instance with mock connection
        mock_connection = MagicMock()
        connection_factory = MagicMock(return_value=mock_connection)
        hana = Hana(connection_factory)

        self._setup_healthy_dependencies()
        client = TestClient(app)

        # Initially healthy
        response = client.get("/healthz")
        assert response.status_code == HTTP_200_OK
        assert response.json()["is_hana_healthy"] is True

        # When: Mark connection as unhealthy
        hana.mark_unhealthy()

        # Then: Probe should return 503
        response = client.get("/healthz")
        assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE
        assert response.json()["is_hana_healthy"] is False

    @pytest.mark.asyncio
    async def test_healthz_reflects_background_health_check_failure(self):
        """Test that healthz probe returns 503 when background health check fails."""
        # Given: Create a Hana instance with a connection that fails health checks
        mock_cursor = MagicMock()
        mock_cursor.execute.side_effect = Exception("Connection lost")

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        connection_factory = MagicMock(return_value=mock_connection)
        hana = Hana(connection_factory)

        self._setup_healthy_dependencies()
        client = TestClient(app)

        # When: Execute health check (simulating background task)
        result = await hana._execute_health_check()
        assert result is False

        # Update health status to reflect failed check
        hana._health_status = False

        # Then: Probe should return 503
        response = client.get("/healthz")
        assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE
        assert response.json()["is_hana_healthy"] is False

    @pytest.mark.asyncio
    async def test_healthz_reflects_background_health_check_success(self):
        """Test that healthz probe returns 200 when background health check succeeds."""
        # Given: Create a Hana instance with a connection that passes health checks
        mock_cursor = MagicMock()
        mock_cursor.execute = MagicMock()
        mock_cursor.fetchone = MagicMock(return_value=(1,))
        mock_cursor.close = MagicMock()

        mock_connection = MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        connection_factory = MagicMock(return_value=mock_connection)
        hana = Hana(connection_factory)

        self._setup_healthy_dependencies()
        client = TestClient(app)

        # When: Execute health check (simulating background task)
        result = await hana._execute_health_check()
        assert result is True

        # Health status should remain True
        assert hana._health_status is True

        # Then: Probe should return 200
        response = client.get("/healthz")
        assert response.status_code == HTTP_200_OK
        assert response.json()["is_hana_healthy"] is True

    def test_healthz_after_mark_unhealthy_then_recovery(self):
        """Test that healthz can transition from unhealthy back to healthy."""
        # Given: Create a real Hana instance
        mock_connection = MagicMock()
        connection_factory = MagicMock(return_value=mock_connection)
        hana = Hana(connection_factory)

        self._setup_healthy_dependencies()
        client = TestClient(app)

        # Mark as unhealthy
        hana.mark_unhealthy()
        response = client.get("/healthz")
        assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE

        # When: Simulate recovery (background task would do this)
        hana._health_status = True

        # Then: Probe should return 200
        response = client.get("/healthz")
        assert response.status_code == HTTP_200_OK
        assert response.json()["is_hana_healthy"] is True
