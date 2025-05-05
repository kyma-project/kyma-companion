from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE

from main import app
from routers.probes import IHana, ILLMProbe, IRedis, IUsageTrackerProbe
from services.hana import get_hana
from services.probes import get_llm_probe, get_usage_tracke_probe
from services.redis import get_redis


@pytest.mark.parametrize(
    "test_case, hana_ready, redis_ready, usage_tracker_ready, llm_states, expected_status",
    [
        ("all ready", True, True, True, {"model1": True, "model2": True}, HTTP_200_OK),
        (
            "Hana not ready",
            False,
            True,
            True,
            {"model1": True, "model2": True},
            HTTP_503_SERVICE_UNAVAILABLE,
        ),
        (
            "Redis not ready",
            True,
            False,
            True,
            {"model1": True, "model2": True},
            HTTP_503_SERVICE_UNAVAILABLE,
        ),
        (
            "one model not ready",
            True,
            True,
            True,
            {"model1": False, "model2": True},
            HTTP_503_SERVICE_UNAVAILABLE,
        ),
        ("no models", True, True, True, {}, HTTP_503_SERVICE_UNAVAILABLE),
        (
            "usage_tracker not ready",
            True,
            True,
            False,
            {"model1": True, "model2": True},
            HTTP_503_SERVICE_UNAVAILABLE,
        ),
    ],
)
def test_healthz_probe(
    test_case,
    hana_ready,
    redis_ready,
    usage_tracker_ready,
    llm_states,
    expected_status,
):
    """
    Test the health probe endpoint. This test ensures that the endpoint returns the correct status code.
    """
    # Given:
    mock_hana_conn = MagicMock(spec=IHana)
    mock_hana_conn.is_connection_operational = MagicMock(return_value=hana_ready)
    app.dependency_overrides[get_hana] = lambda: mock_hana_conn

    mock_redis = MagicMock(spec=IRedis)
    mock_redis.is_connection_operational = AsyncMock(return_value=redis_ready)
    app.dependency_overrides[get_redis] = lambda: mock_redis

    usage_tracker_probe = MagicMock(spec=IUsageTrackerProbe)
    usage_tracker_probe.is_healthy = MagicMock(return_value=usage_tracker_ready)
    app.dependency_overrides[get_usage_tracke_probe] = lambda: usage_tracker_probe

    mock_llm_probe = MagicMock(spec=ILLMProbe)
    mock_llm_probe.get_llms_states.return_value = llm_states
    app.dependency_overrides[get_llm_probe] = lambda: mock_llm_probe

    client = TestClient(app)

    # When:
    response = client.get("/healthz")

    # Then:
    assert response.status_code == expected_status, test_case

    # Clean up.
    app.dependency_overrides = {}


@pytest.mark.parametrize(
    "test_case, hana_ready, redis_ready, llm_states, expected_status",
    [
        ("all ready", True, True, True, HTTP_200_OK),
        ("no Hana connection", False, True, True, HTTP_503_SERVICE_UNAVAILABLE),
        ("no Redis connection", True, False, True, HTTP_503_SERVICE_UNAVAILABLE),
        ("no models", True, True, False, HTTP_503_SERVICE_UNAVAILABLE),
    ],
)
def test_ready_probe(test_case, hana_ready, redis_ready, llm_states, expected_status):
    """
    Test the readiness probe endpoint. This test ensures that the endpoint returns the correct status code.
    """
    # Given:
    mock_hana = MagicMock(spec=IHana)
    mock_hana.has_connection.return_value = hana_ready
    app.dependency_overrides[get_hana] = lambda: mock_hana

    mock_redis = MagicMock(spec=IRedis)
    mock_redis.has_connection.return_value = redis_ready
    app.dependency_overrides[get_redis] = lambda: mock_redis

    mock_llm_probe = MagicMock(spec=ILLMProbe)
    mock_llm_probe.has_models.return_value = llm_states
    app.dependency_overrides[get_llm_probe] = lambda: mock_llm_probe

    client = TestClient(app)

    # When:
    response = client.get("/readyz")

    # Then:
    assert response.status_code == expected_status, test_case

    # Clean up.
    app.dependency_overrides = {}
