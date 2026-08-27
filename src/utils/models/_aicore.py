"""Inline SAP AI Core client and model adapters (no external tiny-aicore package)."""

import threading
import time
from collections.abc import Generator
from typing import Any, Self

import httpx
from decouple import config
from google import genai
from google.genai import types
from google.oauth2.credentials import Credentials
from langchain_aws import ChatBedrockConverse
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from pydantic import SecretStr, model_validator


class AICoreClient:
    """Fetches OAuth2 tokens and resolves deployment URLs for SAP AI Core."""

    def __init__(self) -> None:
        self._auth_url: str = config("AICORE_AUTH_URL")
        self._base_url: str = config("AICORE_BASE_URL").rstrip("/")
        self._client_id: str = config("AICORE_CLIENT_ID")
        self._client_secret: str = config("AICORE_CLIENT_SECRET")
        self._resource_group: str = config("AICORE_RESOURCE_GROUP", default="default")
        self._token_lock = threading.Lock()
        self._token: str = ""
        self._token_exp: float = 0.0
        self._deployment_lock = threading.Lock()
        self._deployment_cache: dict[str, str] = {}

    def get_token(self) -> str:
        with self._token_lock:
            if self._token and time.time() < self._token_exp:
                return self._token
        resp = httpx.post(
            f"{self._auth_url}/oauth/token",
            data={"grant_type": "client_credentials"},
            auth=(self._client_id, self._client_secret),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp.raise_for_status()
        body = resp.json()
        token = body["access_token"]
        token_exp = time.time() + body["expires_in"] - 60
        with self._token_lock:
            self._token = token
            self._token_exp = token_exp
            return self._token

    def get_deployment_url(self, deployment_id: str) -> str:
        with self._deployment_lock:
            if deployment_id in self._deployment_cache:
                return self._deployment_cache[deployment_id]
        token = self.get_token()
        resp = httpx.get(
            f"{self._base_url}/lm/deployments/{deployment_id}",
            headers={"Authorization": f"Bearer {token}", "AI-Resource-Group": self._resource_group},
        )
        resp.raise_for_status()
        body = resp.json()
        url: str = body.get("deploymentUrl", "")
        if not url:
            raise ValueError(f"Deployment {deployment_id!r} has no deploymentUrl (not running?)")
        with self._deployment_lock:
            self._deployment_cache[deployment_id] = url
        return url


class _BearerAuth(httpx.Auth):
    def __init__(self, client: AICoreClient) -> None:
        self._client = client

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response]:
        request.headers["Authorization"] = f"Bearer {self._client.get_token()}"
        request.headers["AI-Resource-Group"] = self._client._resource_group
        yield request


def make_openai_chat(client: AICoreClient, deployment_id: str, model_name: str, **kwargs: Any) -> ChatOpenAI:
    deployment_url = client.get_deployment_url(deployment_id)
    auth = _BearerAuth(client)
    return ChatOpenAI(
        base_url=deployment_url,
        api_key="placeholder",  # type: ignore[arg-type]
        model=model_name,
        http_client=httpx.Client(auth=auth),
        http_async_client=httpx.AsyncClient(auth=auth),
        **kwargs,
    )


def make_openai_embeddings(client: AICoreClient, deployment_id: str, model_name: str) -> OpenAIEmbeddings:
    deployment_url = client.get_deployment_url(deployment_id)
    auth = _BearerAuth(client)
    return OpenAIEmbeddings(
        base_url=deployment_url,
        api_key="placeholder",  # type: ignore[arg-type]
        model=model_name,
        http_client=httpx.Client(auth=auth),
        http_async_client=httpx.AsyncClient(auth=auth),
    )


class _RefreshingChatBedrockConverse(ChatBedrockConverse):
    aicore_client: Any

    @model_validator(mode="after")
    def _register_token_refresh(self) -> Self:
        aicore = self.aicore_client

        def _inject_token(request: Any, **kwargs: Any) -> None:
            request.headers["Authorization"] = f"Bearer {aicore.get_token()}"
            request.headers["AI-Resource-Group"] = aicore._resource_group

        self.client.meta.events.register("before-send.bedrock-runtime.Converse", _inject_token)
        self.client.meta.events.register("before-send.bedrock-runtime.ConverseStream", _inject_token)
        return self


def make_anthropic_chat(client: AICoreClient, deployment_id: str, model_name: str, **kwargs: Any) -> ChatBedrockConverse:
    deployment_url = client.get_deployment_url(deployment_id)
    return _RefreshingChatBedrockConverse(
        base_url=deployment_url,
        aws_access_key_id=SecretStr("dummy"),
        aws_secret_access_key=SecretStr(client.get_token()),
        region_name="us-east-1",
        model=model_name,
        aicore_client=client,
        **kwargs,
    )


def _rewrite_gemini(request: httpx.Request, client: AICoreClient, deployment_id: str) -> None:
    path = request.url.path
    if "/models/" not in path:
        return
    _, suffix = path.split("/models/", 1)
    if not suffix or suffix.startswith(("/", "?")):
        return
    deployment_url = httpx.URL(client.get_deployment_url(deployment_id))
    new_path = f"{deployment_url.path.rstrip('/')}/models/{suffix}"
    request.url = request.url.copy_with(
        scheme=deployment_url.scheme, host=deployment_url.host,
        port=deployment_url.port, path=new_path,
    )
    request.headers["Host"] = deployment_url.host
    request.headers["Authorization"] = f"Bearer {client.get_token()}"
    request.headers["AI-Resource-Group"] = client._resource_group


class _GeminiTransport(httpx.BaseTransport):
    def __init__(self, client: AICoreClient, deployment_id: str) -> None:
        self._client = client
        self._deployment_id = deployment_id
        self._inner = httpx.HTTPTransport()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        _rewrite_gemini(request, self._client, self._deployment_id)
        return self._inner.handle_request(request)

    def close(self) -> None:
        self._inner.close()


class _AsyncGeminiTransport(httpx.AsyncBaseTransport):
    def __init__(self, client: AICoreClient, deployment_id: str) -> None:
        self._client = client
        self._deployment_id = deployment_id
        self._inner = httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        _rewrite_gemini(request, self._client, self._deployment_id)
        return await self._inner.handle_async_request(request)

    async def aclose(self) -> None:
        await self._inner.aclose()


def make_gemini_client(client: AICoreClient, deployment_id: str) -> genai.Client:
    return genai.Client(
        vertexai=True,
        project="placeholder",
        location="placeholder",
        credentials=Credentials(token="placeholder"),
        http_options=types.HttpOptions(
            client_args={"transport": _GeminiTransport(client, deployment_id)},
            async_client_args={"transport": _AsyncGeminiTransport(client, deployment_id)},
        ),
    )
