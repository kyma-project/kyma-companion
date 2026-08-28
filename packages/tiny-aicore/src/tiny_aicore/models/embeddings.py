"""OpenAI embeddings adapter for SAP AI Core."""

from collections.abc import Generator

import httpx
from langchain_openai import OpenAIEmbeddings

from tiny_aicore.client import AICoreClient

_API_VERSION = "2025-03-01-preview"


class _AICoreAuth(httpx.Auth):
    """httpx Auth that injects a fresh AI Core bearer token on every request."""

    def __init__(self, client: AICoreClient) -> None:
        self._client = client

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response]:
        request.headers["Authorization"] = f"Bearer {self._client.get_token()}"
        request.headers["AI-Resource-Group"] = self._client._resource_group
        yield request


class OpenAIEmbeddingsAdapter:
    """Wraps OpenAIEmbeddings with SAP AI Core deployment URL and per-request token refresh."""

    def __init__(self, client: AICoreClient, deployment_id: str, model_name: str) -> None:
        deployment_url = client.get_deployment_url(deployment_id)
        auth = _AICoreAuth(client)
        self._embeddings = OpenAIEmbeddings(
            base_url=deployment_url,
            api_key="placeholder",  # auth header injected by transport
            model=model_name,
            default_query={"api-version": _API_VERSION},
            http_client=httpx.Client(auth=auth),
            http_async_client=httpx.AsyncClient(auth=auth),
        )

    @property
    def embeddings(self) -> OpenAIEmbeddings:
        """Return the underlying OpenAIEmbeddings instance."""
        return self._embeddings
