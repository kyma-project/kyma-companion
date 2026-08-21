"""Anthropic (Bedrock Converse) adapter for SAP AI Core."""

from collections.abc import Generator
from typing import Any

import httpx
from langchain_aws import ChatBedrockConverse
from pydantic import SecretStr

from tiny_aicore.client import AICoreClient


class _AICoreAuth(httpx.Auth):
    """httpx Auth that injects a fresh AI Core bearer token on every request."""

    def __init__(self, client: AICoreClient) -> None:
        self._client = client

    def auth_flow(self, request: httpx.Request) -> Generator[httpx.Request, httpx.Response, None]:
        request.headers["Authorization"] = f"Bearer {self._client.get_token()}"
        yield request


class AnthropicAdapter:
    """Wraps ChatBedrockConverse with SAP AI Core deployment URL and per-request token refresh."""

    def __init__(self, client: AICoreClient, deployment_id: str, model_name: str, **kwargs: Any) -> None:
        deployment_url = client.get_deployment_url(deployment_id)
        auth = _AICoreAuth(client)
        self._llm = ChatBedrockConverse(
            base_url=deployment_url,
            aws_access_key_id=SecretStr("dummy"),
            aws_secret_access_key=SecretStr("placeholder"),  # auth injected by transport
            region_name="us-east-1",
            model=model_name,
            http_client=httpx.Client(auth=auth),
            http_async_client=httpx.AsyncClient(auth=auth),
            **kwargs,
        )

    @property
    def llm(self) -> ChatBedrockConverse:
        """Return the underlying ChatBedrockConverse instance."""
        return self._llm
