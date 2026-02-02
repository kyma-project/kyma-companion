"""Tests for probe endpoints interaction with Hana query execution."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from hdbcli import dbapi
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE

from main import app
from routers.probes import ILLMProbe, IRedis, IUsageTrackerProbe
from services.hana import Hana
from services.probes import get_llm_probe, get_usage_tracker_probe
from services.redis import get_redis


class TestProbesHana:
    """Tests for probe endpoints that verify Hana query execution behavior."""

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

    def test_healthz_returns_200_when_query_succeeds(self):
        """Test that the healthz probe returns HTTP 200 when the database is fully operational.

        This verifies the happy path where the HANA connection can successfully execute
        the test query. The probe should report the system as healthy to Kubernetes.
        """
        # Given: Hana connection that can execute queries successfully
        mock_cursor = MagicMock()
        mock_cursor.execute = MagicMock()
        mock_cursor.fetchone = MagicMock(return_value=(1,))
        mock_cursor.close = MagicMock()

        mock_connection = MagicMock()
        mock_connection.cursor = MagicMock(return_value=mock_cursor)

        connection_factory = MagicMock(return_value=mock_connection)
        Hana(connection_factory)

        self._setup_healthy_dependencies()
        client = TestClient(app)

        # When: Call health probe
        response = client.get("/healthz")

        # Then: Returns 200 and query was executed
        assert response.status_code == HTTP_200_OK
        assert response.json()["is_hana_healthy"] is True
        mock_cursor.execute.assert_called_with("SELECT 1 FROM DUMMY")
        mock_cursor.fetchone.assert_called_once()
        mock_cursor.close.assert_called_once()

    def test_healthz_returns_503_when_query_fails(self):
        """Test that the healthz probe returns HTTP 503 when the database connection is broken.

        This ensures that operational issues (like connection loss during query execution)
        are properly detected, allowing Kubernetes to restart the pod and restore service.
        """
        # Given: Hana connection that fails query execution
        mock_cursor = MagicMock()
        mock_cursor.execute = MagicMock(side_effect=Exception("Connection lost"))

        mock_connection = MagicMock()
        mock_connection.cursor = MagicMock(return_value=mock_cursor)

        connection_factory = MagicMock(return_value=mock_connection)
        Hana(connection_factory)

        self._setup_healthy_dependencies()
        client = TestClient(app)

        # When: Call health probe
        response = client.get("/healthz")

        # Then: Returns 503
        assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE
        assert response.json()["is_hana_healthy"] is False
        mock_cursor.execute.assert_called_with("SELECT 1 FROM DUMMY")

    def test_healthz_returns_503_on_password_expiry(self):
        """Test that the healthz probe returns HTTP 503 when the database password has expired.

        This verifies that authentication errors like error 414 are properly detected by
        executing a test query. The probe must report unhealthy so Kubernetes can take corrective action.
        """
        # Given: Hana connection that fails with password expiry error
        mock_cursor = MagicMock()
        mock_cursor.execute = MagicMock(side_effect=dbapi.Error(414, "user is forced to change password"))

        mock_connection = MagicMock()
        mock_connection.cursor = MagicMock(return_value=mock_cursor)

        connection_factory = MagicMock(return_value=mock_connection)
        Hana(connection_factory)

        self._setup_healthy_dependencies()
        client = TestClient(app)

        # When: Call health probe
        response = client.get("/healthz")

        # Then: Returns 503 and detects password error
        assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE
        assert response.json()["is_hana_healthy"] is False
        mock_cursor.execute.assert_called_with("SELECT 1 FROM DUMMY")

    def test_healthz_returns_503_when_no_connection(self):
        """Test that the healthz probe returns HTTP 503 when the database connection is missing.

        This verifies the basic sanity check that a non-existent connection is properly
        detected and reported as unhealthy to Kubernetes.
        """
        # Given: No Hana connection
        connection_factory = MagicMock(return_value=None)
        Hana(connection_factory)

        self._setup_healthy_dependencies()
        client = TestClient(app)

        # When: Call health probe
        response = client.get("/healthz")

        # Then: Returns 503
        assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE
        assert response.json()["is_hana_healthy"] is False

    def test_healthz_caches_result_within_ttl(self):
        """Test that the healthz probe caches results within the TTL window.

        This verifies that the health status is cached to avoid excessive database queries,
        while still ensuring that the cache expires after the configured TTL.
        """
        # Given: Hana connection
        mock_cursor = MagicMock()
        mock_cursor.execute = MagicMock()
        mock_cursor.fetchone = MagicMock(return_value=(1,))

        mock_connection = MagicMock()
        mock_connection.cursor = MagicMock(return_value=mock_cursor)

        connection_factory = MagicMock(return_value=mock_connection)
        Hana(connection_factory)

        self._setup_healthy_dependencies()
        client = TestClient(app)

        # Mock time to control cache expiration
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        expected_query_count_after_cache_expiry = 2
        with patch("services.hana.datetime") as mock_datetime:
            # First call - should execute query
            mock_datetime.now.return_value = base_time
            response1 = client.get("/healthz")
            assert response1.status_code == HTTP_200_OK
            assert mock_cursor.execute.call_count == 1

            # Second call within TTL - should use cache
            mock_datetime.now.return_value = base_time + timedelta(seconds=60)
            response2 = client.get("/healthz")
            assert response2.status_code == HTTP_200_OK
            assert mock_cursor.execute.call_count == 1  # Still 1, cache was used

            # Third call after TTL expires - should execute query again
            mock_datetime.now.return_value = base_time + timedelta(seconds=301)
            response3 = client.get("/healthz")
            assert response3.status_code == HTTP_200_OK
            assert mock_cursor.execute.call_count == expected_query_count_after_cache_expiry

    def test_healthz_closes_cursor_even_on_failure(self):
        """Test that the database cursor is properly closed even when query execution fails.

        This verifies proper resource cleanup in failure scenarios, preventing resource
        leaks that could accumulate over time and impact database performance.
        """
        # Given: Hana connection that fails on fetchone
        mock_cursor = MagicMock()
        mock_cursor.execute = MagicMock()
        mock_cursor.fetchone = MagicMock(side_effect=Exception("Fetch failed"))

        mock_connection = MagicMock()
        mock_connection.cursor = MagicMock(return_value=mock_cursor)

        connection_factory = MagicMock(return_value=mock_connection)
        Hana(connection_factory)

        self._setup_healthy_dependencies()
        client = TestClient(app)

        # When: Call health probe
        response = client.get("/healthz")

        # Then: Cursor was closed despite error
        assert response.status_code == HTTP_503_SERVICE_UNAVAILABLE
        mock_cursor.close.assert_called_once()
