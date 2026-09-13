from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.langchain.amazon import ChatBedrockConverse
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI
from gen_ai_hub.proxy.native.google_genai.clients import Client as GoogleGenAIClient

from utils import settings
from utils.config import ModelConfig
from utils.logging import get_logger
from utils.models.thinking import get_anthropic_thinking_fields
from utils.settings import ThinkingEffort

logger = get_logger(__name__)


class AnthropicModel:
    """Anthropic Claude model via AWS Bedrock Converse API."""

    _name: str
    _llm: ChatBedrockConverse

    def __init__(self, config: ModelConfig, proxy_client: BaseProxyClient):
        self._name = config.name
        thinking_enabled = settings.THINKING_EFFORT != ThinkingEffort.OFF
        # Anthropic requires temperature=1 whenever extended thinking is enabled.
        temperature = 1.0 if thinking_enabled else config.temperature
        logger.info(
            f"Loading Anthropic model '{config.name}' with THINKING_EFFORT={settings.THINKING_EFFORT} "
            f"(thinking {'enabled' if thinking_enabled else 'disabled'})."
        )
        self._llm = ChatBedrockConverse(
            model_name=config.name,
            deployment_id=config.deployment_id,
            proxy_client=proxy_client,
            temperature=temperature,
            additional_model_request_fields=get_anthropic_thinking_fields(settings.THINKING_EFFORT),
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
