from typing import cast

from langchain_aws import ChatBedrockConverse
from langchain_core.language_models import BaseChatModel

from utils.config import ModelConfig
from utils.models._aicore import AICoreClient, make_anthropic_chat


class AnthropicModel:
    """Anthropic Claude model via AWS Bedrock Converse API."""

    _name: str
    _llm: ChatBedrockConverse

    def __init__(self, config: ModelConfig, client: AICoreClient):
        self._name = config.name
        self._llm = cast(
            ChatBedrockConverse,
            make_anthropic_chat(
                client=client,
                deployment_id=config.deployment_id,
                model_name=config.name,
                temperature=config.temperature,
            ),
        )

    def invoke(self, content: str):  # noqa
        """Generate content using the model."""
        return self._llm.invoke(content)

    @property
    def name(self) -> str:
        """Returns the name of the Anthropic model."""
        return self._name

    @property
    def llm(self) -> BaseChatModel:
        """Returns the instance of the Anthropic model."""
        return self._llm
