from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.langchain.amazon import ChatBedrockConverse
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI
from gen_ai_hub.proxy.native.google_genai.clients import Client as GoogleGenAIClient

from utils import settings
from utils.config import ModelConfig


class AnthropicModel:
    """Anthropic Claude model via AWS Bedrock Converse API."""

    _name: str
    _llm: ChatBedrockConverse

    def __init__(self, config: ModelConfig, proxy_client: BaseProxyClient):
        self._name = config.name
        self._llm = ChatBedrockConverse(
            model_name=config.name,
            deployment_id=config.deployment_id,
            proxy_client=proxy_client,
            temperature=config.temperature,
        )

    def invoke(self, content: str):  # noqa
        """Generate content using the model."""
        return self._llm.invoke(content)

    @property
    def name(self) -> str:
        """Returns the name of the Anthropic model."""
        return self._name

    @property
    def llm(self) -> ChatOpenAI | GoogleGenAIClient | ChatBedrockConverse:
        """Returns the instance of the Anthropic model."""
        return self._llm
