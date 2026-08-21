"""Integration tests for tiny-aicore using respx to mock all HTTP calls.

These tests exercise the full construction and request path of each adapter
without real credentials.
"""

import json
from unittest.mock import patch

import httpx
import pytest
import respx

AUTH_URL = "https://auth.example.com"
BASE_URL = "https://api.example.com"
DEPLOYMENT_URL = "https://dep.example.com/v1"
DEPLOYMENT_ID = "dep-abc123"
TOKEN = "test-bearer-token"

ENV = {
    "AICORE_AUTH_URL": AUTH_URL,
    "AICORE_BASE_URL": BASE_URL,
    "AICORE_CLIENT_ID": "cid",
    "AICORE_CLIENT_SECRET": "csecret",
    "AICORE_RESOURCE_GROUP": "default",
}


def _token_body() -> dict:
    return {"access_token": TOKEN, "expires_in": 3600}


def _deployment_body() -> dict:
    return {"deploymentUrl": DEPLOYMENT_URL}


@pytest.fixture()
def aicore_client():
    with patch.dict("os.environ", ENV):
        from tiny_aicore.client import AICoreClient

        return AICoreClient()


@respx.mock
def test_client_get_token(aicore_client) -> None:  # type: ignore[no-untyped-def]
    respx.post(f"{AUTH_URL}/oauth/token").mock(
        return_value=httpx.Response(200, json=_token_body())
    )
    token = aicore_client.get_token()
    assert token == TOKEN


@respx.mock
def test_client_get_deployment_url(aicore_client) -> None:  # type: ignore[no-untyped-def]
    respx.post(f"{AUTH_URL}/oauth/token").mock(
        return_value=httpx.Response(200, json=_token_body())
    )
    respx.get(f"{BASE_URL}/lm/deployments/{DEPLOYMENT_ID}").mock(
        return_value=httpx.Response(200, json=_deployment_body())
    )
    url = aicore_client.get_deployment_url(DEPLOYMENT_ID)
    assert url == DEPLOYMENT_URL


@respx.mock
def test_openai_adapter_sends_bearer_token(aicore_client) -> None:  # type: ignore[no-untyped-def]
    from tiny_aicore.models.openai import OpenAIAdapter

    respx.post(f"{AUTH_URL}/oauth/token").mock(
        return_value=httpx.Response(200, json=_token_body())
    )
    respx.get(f"{BASE_URL}/lm/deployments/{DEPLOYMENT_ID}").mock(
        return_value=httpx.Response(200, json=_deployment_body())
    )
    chat_route = respx.post(f"{DEPLOYMENT_URL}/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": "hello"},
                        "finish_reason": "stop",
                    }
                ],
                "model": "gpt-4",
                "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
            },
        )
    )

    adapter = OpenAIAdapter(aicore_client, DEPLOYMENT_ID, "gpt-4")
    adapter.llm.invoke("hi")

    assert chat_route.called
    auth_header = chat_route.calls[0].request.headers.get("authorization", "")
    assert auth_header == f"Bearer {TOKEN}"


@respx.mock
def test_embeddings_adapter_sends_bearer_token(aicore_client) -> None:  # type: ignore[no-untyped-def]
    from tiny_aicore.models.embeddings import OpenAIEmbeddingsAdapter

    respx.post(f"{AUTH_URL}/oauth/token").mock(
        return_value=httpx.Response(200, json=_token_body())
    )
    respx.get(f"{BASE_URL}/lm/deployments/{DEPLOYMENT_ID}").mock(
        return_value=httpx.Response(200, json=_deployment_body())
    )
    embed_route = respx.post(f"{DEPLOYMENT_URL}/embeddings").mock(
        return_value=httpx.Response(
            200,
            json={
                "object": "list",
                "data": [{"object": "embedding", "index": 0, "embedding": [0.1, 0.2, 0.3]}],
                "model": "text-embedding-ada-002",
                "usage": {"prompt_tokens": 3, "total_tokens": 3},
            },
        )
    )

    adapter = OpenAIEmbeddingsAdapter(aicore_client, DEPLOYMENT_ID, "text-embedding-ada-002")
    adapter.embeddings.embed_query("hello")

    assert embed_route.called
    auth_header = embed_route.calls[0].request.headers.get("authorization", "")
    assert auth_header == f"Bearer {TOKEN}"


@respx.mock
def test_openai_adapter_refreshes_token_on_expiry(aicore_client) -> None:  # type: ignore[no-untyped-def]
    """Token fetched at request time, not baked at construction."""
    import time

    from tiny_aicore.models.openai import OpenAIAdapter

    token_responses = [
        httpx.Response(200, json={"access_token": "tok1", "expires_in": 3600}),
        httpx.Response(200, json={"access_token": "tok2", "expires_in": 3600}),
    ]
    respx.post(f"{AUTH_URL}/oauth/token").mock(side_effect=token_responses)
    respx.get(f"{BASE_URL}/lm/deployments/{DEPLOYMENT_ID}").mock(
        return_value=httpx.Response(200, json=_deployment_body())
    )
    chat_route = respx.post(f"{DEPLOYMENT_URL}/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}],
                "model": "gpt-4",
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )
    )

    adapter = OpenAIAdapter(aicore_client, DEPLOYMENT_ID, "gpt-4")

    # First call uses tok1
    adapter.llm.invoke("hi")
    assert chat_route.calls[0].request.headers["authorization"] == "Bearer tok1"

    # Expire the token
    aicore_client._token_exp = time.time() - 1

    # Second call fetches tok2
    adapter.llm.invoke("hi")
    assert chat_route.calls[1].request.headers["authorization"] == "Bearer tok2"
