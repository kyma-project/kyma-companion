"""Unit tests for AICoreClient."""

import time
from unittest.mock import MagicMock, patch

import pytest
from tiny_aicore.client import AICoreClient


def _make_client() -> AICoreClient:
    with patch.dict(
        "os.environ",
        {
            "AICORE_AUTH_URL": "https://auth.example.com",
            "AICORE_BASE_URL": "https://api.example.com/",
            "AICORE_CLIENT_ID": "cid",
            "AICORE_CLIENT_SECRET": "csecret",
            "AICORE_RESOURCE_GROUP": "default",
        },
    ):
        return AICoreClient()


def _token_response(token: str = "tok1", expires_in: int = 3600) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"access_token": token, "expires_in": expires_in}
    resp.raise_for_status = MagicMock()
    return resp


def _deployment_response(url: str = "https://dep.example.com/v1") -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"deploymentUrl": url}
    resp.raise_for_status = MagicMock()
    return resp


class TestGetToken:
    def test_fetches_token_on_first_call(self) -> None:
        client = _make_client()
        with patch("httpx.post", return_value=_token_response("tok1")) as mock_post:
            token = client.get_token()
        assert token == "tok1"
        mock_post.assert_called_once()

    def test_returns_cached_token_on_second_call(self) -> None:
        client = _make_client()
        with patch("httpx.post", return_value=_token_response("tok1")) as mock_post:
            client.get_token()
            token = client.get_token()
        assert token == "tok1"
        mock_post.assert_called_once()  # only one HTTP call

    def test_refetches_expired_token(self) -> None:
        client = _make_client()
        responses = [_token_response("tok1", expires_in=0), _token_response("tok2")]
        with patch("httpx.post", side_effect=responses) as mock_post:
            client.get_token()
            # expire it
            client._token_exp = time.time() - 1
            token = client.get_token()
        assert token == "tok2"
        assert mock_post.call_count == 2

    def test_http_call_not_under_lock(self) -> None:
        """get_token() must not hold the lock while doing the HTTP POST."""
        client = _make_client()
        lock_held_during_post: list[bool] = []

        def patched_post(*args, **kwargs):  # type: ignore[no-untyped-def]
            lock_held_during_post.append(client._token_lock.locked())
            return _token_response("tok1")

        with patch("httpx.post", side_effect=patched_post):
            client.get_token()

        assert lock_held_during_post == [False]


class TestGetDeploymentUrl:
    def test_fetches_and_caches_deployment_url(self) -> None:
        client = _make_client()
        with (
            patch("httpx.post", return_value=_token_response()),
            patch("httpx.get", return_value=_deployment_response("https://dep.example.com")) as mock_get,
        ):
            url = client.get_deployment_url("dep-123")
            url2 = client.get_deployment_url("dep-123")
        assert url == "https://dep.example.com"
        assert url2 == "https://dep.example.com"
        mock_get.assert_called_once()  # cached on second call

    def test_raises_on_missing_deployment_url(self) -> None:
        client = _make_client()
        resp = MagicMock()
        resp.json.return_value = {}
        resp.raise_for_status = MagicMock()
        with (
            patch("httpx.post", return_value=_token_response()),
            patch("httpx.get", return_value=resp),
            pytest.raises(ValueError, match="no deploymentUrl"),
        ):
            client.get_deployment_url("dep-missing")

    def test_base_url_trailing_slash_stripped(self) -> None:
        client = _make_client()
        assert not client._base_url.endswith("/")
