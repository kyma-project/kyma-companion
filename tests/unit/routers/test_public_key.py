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

    async def save_public_key(self, session_id: str, public_key: str) -> None:
        if self.should_fail:
            raise RuntimeError("encryption cache save failed")
        self.saved[session_id] = (public_key, REDIS_TTL)


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_post_public_key_success(monkeypatch: pytest.MonkeyPatch):
    encryption_cache = MockEncryptionCache()

    app.dependency_overrides[get_encryption_cache] = lambda: encryption_cache
    monkeypatch.setattr(public_key, "ENCRYPTION_PUBLIC_KEY_B64", "companion-public-key")
    monkeypatch.setattr(public_key, "create_session_id", lambda: "session-123")

    client = TestClient(app)
    response = client.post(
        "/api/public-key",
        json={"public_key": "request-public-key"},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "session_id": "session-123",
        "companion_public_key": "companion-public-key",
    }
    assert encryption_cache.saved["session-123"] == ("request-public-key", REDIS_TTL)


def test_post_public_key_returns_500_when_redis_write_fails(monkeypatch: pytest.MonkeyPatch):
    encryption_cache = MockEncryptionCache(should_fail=True)

    app.dependency_overrides[get_encryption_cache] = lambda: encryption_cache
    monkeypatch.setattr(public_key, "ENCRYPTION_PUBLIC_KEY_B64", "companion-public-key")

    client = TestClient(app)
    response = client.post(
        "/api/public-key",
        json={"public_key": "request-public-key"},
    )

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


def test_post_public_key_returns_500_when_companion_key_missing(monkeypatch: pytest.MonkeyPatch):
    encryption_cache = MockEncryptionCache()

    app.dependency_overrides[get_encryption_cache] = lambda: encryption_cache
    monkeypatch.setattr(public_key, "ENCRYPTION_PUBLIC_KEY_B64", "")

    client = TestClient(app)
    response = client.post(
        "/api/public-key",
        json={"public_key": "request-public-key"},
    )

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


def test_post_public_key_returns_422_when_public_key_missing():
    app.dependency_overrides[get_encryption_cache] = lambda: MockEncryptionCache()

    client = TestClient(app)
    response = client.post("/api/public-key", json={})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
