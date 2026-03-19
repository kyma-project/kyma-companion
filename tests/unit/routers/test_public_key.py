from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from main import app
from routers import public_key
from services.encryption_cache import get_encryption_cache
from utils.settings import REDIS_TTL


class MockEncryptionCache:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.saved: dict[str, tuple[str, int | None]] = {}

    async def save_client_public_key(self, session_id: str, public_key: str) -> None:
        if self.should_fail:
            raise RuntimeError("encryption cache save failed")
        self.saved[session_id] = (public_key, REDIS_TTL)


@pytest.mark.parametrize(
    "description, companion_key, should_fail, request_body, expected_status, expected_body, expected_saved",
    [
        pytest.param(
            "valid request stores the client public key and returns session ID and companion public key",
            "companion-public-key",
            False,
            {"public_key": "request-public-key"},
            HTTPStatus.OK,
            {"session_id": "session-123", "companion_public_key": "companion-public-key"},
            ("request-public-key", REDIS_TTL),
            id="success",
        ),
        pytest.param(
            "returns 500 when the Redis write raises an exception",
            "companion-public-key",
            True,
            {"public_key": "request-public-key"},
            HTTPStatus.INTERNAL_SERVER_ERROR,
            None,
            None,
            id="redis_write_fails",
        ),
        pytest.param(
            "returns 500 when the companion public key is not configured",
            "",
            False,
            {"public_key": "request-public-key"},
            HTTPStatus.INTERNAL_SERVER_ERROR,
            None,
            None,
            id="companion_key_missing",
        ),
        pytest.param(
            "returns 422 when the request body is missing the public_key field",
            "companion-public-key",
            False,
            {},
            HTTPStatus.UNPROCESSABLE_ENTITY,
            None,
            None,
            id="request_public_key_missing",
        ),
    ],
)
def test_post_public_key(
    monkeypatch: pytest.MonkeyPatch,
    description: str,
    companion_key: str,
    should_fail: bool,
    request_body: dict,
    expected_status: HTTPStatus,
    expected_body: dict | None,
    expected_saved: tuple | None,
):
    encryption_cache = MockEncryptionCache(should_fail=should_fail)
    monkeypatch.setitem(app.dependency_overrides, get_encryption_cache, lambda: encryption_cache)
    monkeypatch.setattr(public_key, "ENCRYPTION_PUBLIC_KEY_B64", companion_key)
    monkeypatch.setattr(public_key, "create_session_id", lambda: "session-123")

    client = TestClient(app)
    response = client.post("/api/public-key", json=request_body)

    assert response.status_code == expected_status, description
    if expected_body is not None:
        assert response.json() == expected_body, description
    if expected_saved is not None:
        assert encryption_cache.saved["session-123"] == expected_saved, description
