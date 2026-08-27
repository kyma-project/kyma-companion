"""Inline SAP AI Core client and OpenAI chat adapter for blackbox tests."""

import threading
import time
from collections.abc import Generator

import httpx
from decouple import config
from langchain_openai import ChatOpenAI


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
        yield request


def make_openai_chat(client: AICoreClient, deployment_id: str, model_name: str, temperature: float) -> ChatOpenAI:
    """Create a ChatOpenAI instance routed through SAP AI Core."""
    deployment_url = client.get_deployment_url(deployment_id)
    auth = _BearerAuth(client)
    return ChatOpenAI(
        base_url=deployment_url,
        api_key="placeholder",  # type: ignore[arg-type]
        model=model_name,
        temperature=temperature,
        http_client=httpx.Client(auth=auth),
        http_async_client=httpx.AsyncClient(auth=auth),
    )
