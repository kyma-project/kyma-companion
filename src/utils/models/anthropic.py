from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.langchain import init_llm

from utils.config import ModelConfig


class AnthropicModel:
    """Anthropic Model via SAP AI SDK (ChatBedrockConverse)."""

    _name: str
    _llm: object  # ChatBedrockConverse

    def __init__(self, config: ModelConfig, proxy_client: BaseProxyClient):
        self._name = config.name
        self._llm = init_llm(
            config.name,
            proxy_client=proxy_client,
            temperature=config.temperature,
            max_tokens=4096,
        )
        # Anthropic doesn't allow temperature + top_p together
        if hasattr(self._llm, "top_p"):
            self._llm.top_p = None

    def invoke(self, content: str):  # noqa
        """Generate content using the model"""
        response = self.llm.invoke(content)
        return response

    @property
    def name(self) -> str:
        """Returns the name of the Anthropic model."""
        return self._name

    @property
    def llm(self):
        """Returns the instance of Anthropic model."""
        return self._llm
