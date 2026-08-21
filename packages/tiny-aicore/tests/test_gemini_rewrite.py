"""Unit tests for the Gemini _rewrite() URL rewriting logic."""

from unittest.mock import MagicMock

import httpx

from tiny_aicore.models.gemini import _rewrite


def _make_client(token: str = "gemini-token", deployment_url: str = "https://dep.example.com/v1") -> MagicMock:
    mock = MagicMock()
    mock.get_token.return_value = token
    mock.get_deployment_url.return_value = deployment_url
    return mock


def _request(path: str) -> httpx.Request:
    return httpx.Request("POST", f"https://generativelanguage.googleapis.com{path}")


class TestRewrite:
    def test_rewrites_model_path(self) -> None:
        client = _make_client(deployment_url="https://dep.example.com/v1")
        req = _request("/v1beta/models/gemini-pro:generateContent")
        _rewrite(req, client, "dep-123")
        assert req.url.host == "dep.example.com"
        assert "/models/gemini-pro:generateContent" in req.url.path

    def test_injects_authorization_header(self) -> None:
        client = _make_client(token="fresh-token")
        req = _request("/v1beta/models/gemini-pro:generateContent")
        _rewrite(req, client, "dep-123")
        assert req.headers["Authorization"] == "Bearer fresh-token"

    def test_skips_non_model_paths(self) -> None:
        client = _make_client()
        original_url = "https://generativelanguage.googleapis.com/v1beta/other"
        req = httpx.Request("GET", original_url)
        _rewrite(req, client, "dep-123")
        assert str(req.url) == original_url
        client.get_deployment_url.assert_not_called()

    def test_skips_empty_suffix(self) -> None:
        client = _make_client()
        req = _request("/v1beta/models/")
        original_host = req.url.host
        _rewrite(req, client, "dep-123")
        assert req.url.host == original_host

    def test_calls_get_token_per_request(self) -> None:
        client = _make_client()
        req1 = _request("/v1beta/models/gemini-pro:generateContent")
        req2 = _request("/v1beta/models/gemini-pro:generateContent")
        _rewrite(req1, client, "dep-123")
        _rewrite(req2, client, "dep-123")
        assert client.get_token.call_count == 2
