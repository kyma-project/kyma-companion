"""OpenAI embeddings adapter for SAP AI Core."""

from collections.abc import Generator

import httpx
from langchain_openai import OpenAIEmbeddings

from tiny_aicore.client import AICoreClient


class _AICoreAuth(httpx.Auth):
    """httpx Auth that injects a fresh AI Core bearer token on every request."""

    def __init__(self, client: AICoreClient) -> None:
        self._client = client

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response]:
        request.headers["Authorization"] = f"Bearer {self._client.get_token()}"
        yield request


class OpenAIEmbeddingsAdapter:
    """Wraps OpenAIEmbeddings with SAP AI Core deployment URL and per-request token refresh."""

    def __init__(self, client: AICoreClient, deployment_id: str, model_name: str) -> None:
        deployment_url = client.get_deployment_url(deployment_id)
        auth = _AICoreAuth(client)
        self._embeddings = OpenAIEmbeddings(
            base_url=deployment_url,
            api_key="placeholder",  # type: ignore[arg-type]  # auth header injected by transport
            model=model_name,
            http_client=httpx.Client(auth=auth),
            http_async_client=httpx.AsyncClient(auth=auth),
        )

    @property
    def embeddings(self) -> OpenAIEmbeddings:
        """Return the underlying OpenAIEmbeddings instance."""
        return self._embeddings
