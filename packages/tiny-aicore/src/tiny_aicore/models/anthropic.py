"""Anthropic (Bedrock Converse) adapter for SAP AI Core."""

from typing import Any, Self
from urllib.parse import urlparse

from langchain_aws import ChatBedrockConverse
from pydantic import SecretStr, model_validator

from tiny_aicore.client import AICoreClient


class _RefreshingChatBedrockConverse(ChatBedrockConverse):
    """ChatBedrockConverse that rewrites the botocore URL and injects a fresh AI Core bearer token."""

    aicore_client: Any  # AICoreClient — typed Any to keep Pydantic schema simple
    aicore_deployment_id: Any

    @model_validator(mode="after")
    def _register_token_refresh(self) -> Self:
        aicore = self.aicore_client
        deployment_id = self.aicore_deployment_id

        def _rewrite_and_inject(request: Any, **kwargs: Any) -> None:
            # botocore builds /model/<model-id>/converse; AI Core expects <deployment_url>/converse.
            deployment_url = aicore.get_deployment_url(deployment_id)
            last_segment = urlparse(request.url).path.rsplit("/", 1)[-1]
            request.url = f"{deployment_url.rstrip('/')}/{last_segment}"
            request.headers["Authorization"] = f"Bearer {aicore.get_token()}"
            request.headers["AI-Resource-Group"] = aicore._resource_group

        self.client.meta.events.register("before-send.bedrock-runtime.Converse", _rewrite_and_inject)
        self.client.meta.events.register("before-send.bedrock-runtime.ConverseStream", _rewrite_and_inject)
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
            aicore_deployment_id=deployment_id,
            **kwargs,
        )

    @property
    def llm(self) -> ChatBedrockConverse:
        """Return the underlying ChatBedrockConverse instance."""
        return self._llm
