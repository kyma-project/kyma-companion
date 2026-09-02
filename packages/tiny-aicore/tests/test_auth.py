"""Unit tests for _AICoreAuth (shared by OpenAI and Embeddings adapters)."""

from unittest.mock import MagicMock

import httpx
import pytest
from tiny_aicore.models.openai import _AICoreAuth


def _make_request(url: str = "https://example.com/v1/chat") -> httpx.Request:
    return httpx.Request("POST", url)


class TestAICoreAuth:
    def test_injects_authorization_header(self) -> None:
        mock_client = MagicMock()
        mock_client.get_token.return_value = "mytoken"
        auth = _AICoreAuth(mock_client)
        request = _make_request()

        flow = auth.auth_flow(request)
        sent_request = next(flow)

        assert sent_request.headers["Authorization"] == "Bearer mytoken"

    def test_calls_get_token_on_each_request(self) -> None:
        mock_client = MagicMock()
        mock_client.get_token.side_effect = ["tok1", "tok2"]
        auth = _AICoreAuth(mock_client)

        req1 = _make_request()
        next(auth.auth_flow(req1))
        req2 = _make_request()
        next(auth.auth_flow(req2))

        assert req1.headers["Authorization"] == "Bearer tok1"
        assert req2.headers["Authorization"] == "Bearer tok2"
        assert mock_client.get_token.call_count == 2

    def test_flow_is_generator(self) -> None:
        mock_client = MagicMock()
        mock_client.get_token.return_value = "tok"
        auth = _AICoreAuth(mock_client)
        flow = auth.auth_flow(_make_request())
        next(flow)
        with pytest.raises(StopIteration):
            next(flow)
