"""E2E tests for tiny-aicore against real SAP AI Core endpoints.

Requires environment variables from INTEGRATION_TEST_CONFIG:
  AICORE_AUTH_URL, AICORE_BASE_URL, AICORE_CLIENT_ID,
  AICORE_CLIENT_SECRET, AICORE_RESOURCE_GROUP,
  AICORE_DEPLOYMENT_ID_OPENAI, AICORE_DEPLOYMENT_ID_EMBEDDINGS,
  AICORE_DEPLOYMENT_ID_ANTHROPIC
"""

import os

import pytest
from tiny_aicore.client import AICoreClient


def _deployment(var: str) -> str:
    val = os.environ.get(var, "")
    if not val:
        pytest.skip(f"{var} not set")
    return val


@pytest.fixture(scope="module")
def client() -> AICoreClient:
    """Shared AICoreClient for all e2e tests."""
    return AICoreClient()


def test_openai_chat(client: AICoreClient) -> None:
    """OpenAIAdapter can reach the model and get a non-empty response."""
    from tiny_aicore.models.openai import OpenAIAdapter

    deployment_id = _deployment("AICORE_DEPLOYMENT_ID_OPENAI")
    adapter = OpenAIAdapter(client, deployment_id, "gpt-4.1-mini")
    response = adapter.llm.invoke("hi")
    assert response.content


def test_openai_embeddings(client: AICoreClient) -> None:
    """OpenAIEmbeddingsAdapter can reach the model and get a non-empty embedding."""
    from tiny_aicore.models.embeddings import OpenAIEmbeddingsAdapter

    deployment_id = _deployment("AICORE_DEPLOYMENT_ID_EMBEDDINGS")
    adapter = OpenAIEmbeddingsAdapter(client, deployment_id, "text-embedding-3-large")
    result = adapter.embeddings.embed_query("hello")
    assert len(result) > 0


def test_anthropic_chat(client: AICoreClient) -> None:
    """AnthropicAdapter can reach the model and get a non-empty response."""
    from tiny_aicore.models.anthropic import AnthropicAdapter

    deployment_id = _deployment("AICORE_DEPLOYMENT_ID_ANTHROPIC")
    adapter = AnthropicAdapter(client, deployment_id, "anthropic.claude-haiku-4-5")
    response = adapter.llm.invoke("hi")
    assert response.content
