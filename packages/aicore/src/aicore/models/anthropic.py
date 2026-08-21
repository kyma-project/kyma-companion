"""Anthropic (Bedrock Converse) adapter for SAP AI Core."""

from typing import Any

from langchain_aws import ChatBedrockConverse
from pydantic import SecretStr

from aicore.client import AICoreClient


class AnthropicAdapter:
    """Wraps ChatBedrockConverse with SAP AI Core deployment URL and bearer token."""

    def __init__(self, client: AICoreClient, deployment_id: str, model_name: str, **kwargs: Any) -> None:
        deployment_url = client.get_deployment_url(deployment_id)
        token = client.get_token()
        self._llm = ChatBedrockConverse(
            base_url=deployment_url,
            aws_access_key_id=SecretStr("dummy"),
            aws_secret_access_key=SecretStr(token),
            region_name="us-east-1",
            model=model_name,
            **kwargs,
        )

    @property
    def llm(self) -> ChatBedrockConverse:
        """Return the underlying ChatBedrockConverse instance."""
        return self._llm
