"""Anthropic (Bedrock Converse) adapter for SAP AI Core."""

from typing import Any, Self

from langchain_aws import ChatBedrockConverse
from pydantic import SecretStr, model_validator

from tiny_aicore.client import AICoreClient


class _RefreshingChatBedrockConverse(ChatBedrockConverse):
    """ChatBedrockConverse that injects a fresh AI Core bearer token before every request."""

    aicore_client: Any  # AICoreClient — typed Any to keep Pydantic schema simple

    @model_validator(mode="after")
    def _register_token_refresh(self) -> Self:
        aicore = self.aicore_client

        def _inject_token(request: Any, **kwargs: Any) -> None:
            request.headers["Authorization"] = f"Bearer {aicore.get_token()}"

        self.client.meta.events.register("before-send.bedrock-runtime.Converse", _inject_token)
        self.client.meta.events.register("before-send.bedrock-runtime.ConverseStream", _inject_token)
        return self


class AnthropicAdapter:
    """Wraps ChatBedrockConverse with SAP AI Core deployment URL and per-request token refresh."""

    def __init__(self, client: AICoreClient, deployment_id: str, model_name: str, **kwargs: Any) -> None:
        deployment_url = client.get_deployment_url(deployment_id)
        self._llm = _RefreshingChatBedrockConverse(
            base_url=deployment_url,
            aws_access_key_id=SecretStr("dummy"),
            aws_secret_access_key=SecretStr(client.get_token()),  # initial value; refreshed per-request
            region_name="us-east-1",
            model=model_name,
            aicore_client=client,
            **kwargs,
        )

    @property
    def llm(self) -> ChatBedrockConverse:
        """Return the underlying ChatBedrockConverse instance."""
        return self._llm
