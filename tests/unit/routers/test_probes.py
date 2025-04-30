from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE

from main import app
from services.hana import get_hana_connection
from services.probes import get_llm_readiness_probe
from services.redis import get_redis_connection


@pytest.mark.parametrize(
    "hana_ready, redis_ready, llm_states, expected_status",
    [
        (True, True, {"model1": True, "model2": True}, HTTP_200_OK),
        (False, True, {"model1": True, "model2": True}, HTTP_503_SERVICE_UNAVAILABLE),
        (True, False, {"model1": True, "model2": True}, HTTP_503_SERVICE_UNAVAILABLE),
        (True, True, {"model1": False, "model2": True}, HTTP_503_SERVICE_UNAVAILABLE),
        (True, True, {}, HTTP_503_SERVICE_UNAVAILABLE),
    ],
)
def test_healthz_probe_table(hana_ready, redis_ready, llm_states, expected_status):
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

    response = client.get("/healthz")
    assert response.status_code == expected_status


@pytest.mark.parametrize(
    "hana_ready, redis_ready, llm_states, expected_status",
    [
        (True, True, True, HTTP_200_OK),
        (False, True, True, HTTP_503_SERVICE_UNAVAILABLE),
        (True, False, True, HTTP_503_SERVICE_UNAVAILABLE),
        (True, True, False, HTTP_503_SERVICE_UNAVAILABLE),
    ],
)
def test_ready_probe_table(hana_ready, redis_ready, llm_states, expected_status):
    mock_hana_conn = MagicMock() if hana_ready else None
    app.dependency_overrides[get_hana_connection] = lambda: mock_hana_conn

    mock_redis_conn = MagicMock() if redis_ready else None
    app.dependency_overrides[get_redis_connection] = lambda: mock_redis_conn

    mock_llm_probe = MagicMock()
    mock_llm_probe.has_models.return_value = llm_states
    app.dependency_overrides[get_llm_readiness_probe] = lambda: mock_llm_probe

    client = TestClient(app)

    response = client.get("/readyz")
    assert response.status_code == expected_status
