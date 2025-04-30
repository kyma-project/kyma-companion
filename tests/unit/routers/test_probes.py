from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE

from main import app
from services.hana import get_hana_connection
from services.probes import get_llm_readiness_probe
from services.redis import get_redis_connection


@pytest.mark.parametrize(
    "test_case, hana_ready, redis_ready, llm_states, expected_status",
    [
        ("all ready", True, True, {"model1": True, "model2": True}, HTTP_200_OK),
        (
            "Hana not ready",
            False,
            True,
            {"model1": True, "model2": True},
            HTTP_503_SERVICE_UNAVAILABLE,
        ),
        (
            "Redis not ready",
            True,
            False,
            {"model1": True, "model2": True},
            HTTP_503_SERVICE_UNAVAILABLE,
        ),
        (
            "one model not ready",
            True,
            True,
            {"model1": False, "model2": True},
            HTTP_503_SERVICE_UNAVAILABLE,
        ),
        ("no models", True, True, {}, HTTP_503_SERVICE_UNAVAILABLE),
    ],
)
def test_healthz_probe_table(
    test_case, hana_ready, redis_ready, llm_states, expected_status
):
    """
    Test the health probe endpoint. This test ensures that the endpoint returns the correct status code.
    """
    # Given:
    mock_hana_conn = MagicMock()
    mock_hana_conn.isconnected.return_value = hana_ready
    app.dependency_overrides[get_hana_connection] = lambda: mock_hana_conn

    mock_redis_conn = MagicMock()
    mock_redis_conn.ping.return_value = redis_ready
    app.dependency_overrides[get_redis_connection] = lambda: mock_redis_conn

    mock_llm_probe = MagicMock()
    mock_llm_probe.get_llms_states.return_value = llm_states
    app.dependency_overrides[get_llm_readiness_probe] = lambda: mock_llm_probe

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
def test_ready_probe_table(
    test_case, hana_ready, redis_ready, llm_states, expected_status
):
    """
    Test the readiness probe endpoint. This test ensures that the endpoint returns the correct status code.
    """
    # Given:
    mock_hana_conn = MagicMock() if hana_ready else None
    app.dependency_overrides[get_hana_connection] = lambda: mock_hana_conn

    mock_redis_conn = MagicMock() if redis_ready else None
    app.dependency_overrides[get_redis_connection] = lambda: mock_redis_conn

    mock_llm_probe = MagicMock()
    mock_llm_probe.has_models.return_value = llm_states
    app.dependency_overrides[get_llm_readiness_probe] = lambda: mock_llm_probe

    client = TestClient(app)

    # When:
    response = client.get("/readyz")

    # Then:
    assert response.status_code == expected_status, test_case

    # Clean up.
    app.dependency_overrides = {}
