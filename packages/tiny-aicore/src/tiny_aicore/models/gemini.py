"""Gemini adapter for SAP AI Core via custom httpx transport."""

import httpx
from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials

from tiny_aicore.client import AICoreClient


class _AICoreTransport(httpx.BaseTransport):
    """Synchronous httpx transport that rewrites Google GenAI requests to route through AI Core."""

    def __init__(self, client: AICoreClient, deployment_id: str) -> None:
        self._client = client
        self._deployment_id = deployment_id
        self._inner = httpx.HTTPTransport()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Rewrite URL and inject auth header, then forward."""
        _rewrite(request, self._client, self._deployment_id)
        return self._inner.handle_request(request)

    def close(self) -> None:
        """Close the inner transport."""
        self._inner.close()


class _AsyncAICoreTransport(httpx.AsyncBaseTransport):
    """Async httpx transport that rewrites Google GenAI requests to route through AI Core."""

    def __init__(self, client: AICoreClient, deployment_id: str) -> None:
        self._client = client
        self._deployment_id = deployment_id
        self._inner = httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Rewrite URL and inject auth header, then forward."""
        _rewrite(request, self._client, self._deployment_id)
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        """Close the inner transport."""
        await self._inner.aclose()


def _rewrite(request: httpx.Request, client: AICoreClient, deployment_id: str) -> None:
    """Rewrite a Google GenAI httpx request to route through AI Core in-place."""
    path = request.url.path
    if "/models/" not in path:
        return

    _, suffix = path.split("/models/", 1)
    if not suffix or suffix.startswith(("/", "?")):
        return

    deployment_url = httpx.URL(client.get_deployment_url(deployment_id))
    new_path = f"{deployment_url.path.rstrip('/')}/models/{suffix}"
    request.url = request.url.copy_with(
        scheme=deployment_url.scheme,
        host=deployment_url.host,
        port=deployment_url.port,
        path=new_path,
    )
    token = client.get_token()
    request.headers["Host"] = deployment_url.host
    request.headers["Authorization"] = f"Bearer {token}"
    request.headers["AI-Resource-Group"] = client._resource_group


class GeminiAdapter:
    """Wraps google.genai.Client with SAP AI Core routing."""

    def __init__(self, client: AICoreClient, deployment_id: str) -> None:
        self._model = genai.Client(
            vertexai=True,
            project="placeholder",
            location="placeholder",
            credentials=Credentials(token="placeholder"),
            http_options=types.HttpOptions(
                client_args={"transport": _AICoreTransport(client, deployment_id)},
                async_client_args={"transport": _AsyncAICoreTransport(client, deployment_id)},
            ),
        )

    @property
    def llm(self) -> genai.Client:
        """Return the underlying google.genai.Client instance."""
        return self._model
