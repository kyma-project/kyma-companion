from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient

from main import app
from routers import public_key
from services.redis import get_redis


class MockRedisConnection:
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.saved: dict[str, tuple[str, int | None]] = {}

    async def set(self, name: str, value: str, ex: int | None = None) -> bool:
        if self.should_fail:
            raise RuntimeError("redis set failed")
        self.saved[name] = (value, ex)
        return True


class MockRedisService:
    def __init__(self, connection: MockRedisConnection):
        self._connection = connection

    def get_connection(self) -> MockRedisConnection:
        return self._connection


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_post_public_key_success(monkeypatch: pytest.MonkeyPatch):
    redis_connection = MockRedisConnection()

    app.dependency_overrides[get_redis] = lambda: MockRedisService(redis_connection)
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
    assert redis_connection.saved["session-123"] == ("request-public-key", public_key.REDIS_TTL)


def test_post_public_key_returns_500_when_redis_write_fails(monkeypatch: pytest.MonkeyPatch):
    redis_connection = MockRedisConnection(should_fail=True)

    app.dependency_overrides[get_redis] = lambda: MockRedisService(redis_connection)
    monkeypatch.setattr(public_key, "ENCRYPTION_PUBLIC_KEY_B64", "companion-public-key")

    client = TestClient(app)
    response = client.post(
        "/api/public-key",
        json={"public_key": "request-public-key"},
    )

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


def test_post_public_key_returns_500_when_companion_key_missing(monkeypatch: pytest.MonkeyPatch):
    redis_connection = MockRedisConnection()

    app.dependency_overrides[get_redis] = lambda: MockRedisService(redis_connection)
    monkeypatch.setattr(public_key, "ENCRYPTION_PUBLIC_KEY_B64", "")

    client = TestClient(app)
    response = client.post(
        "/api/public-key",
        json={"public_key": "request-public-key"},
    )

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR


def test_post_public_key_returns_422_when_public_key_missing():
    app.dependency_overrides[get_redis] = lambda: MockRedisService(MockRedisConnection())

    client = TestClient(app)
    response = client.post("/api/public-key", json={})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
