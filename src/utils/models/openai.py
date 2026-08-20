from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.langchain.amazon import ChatBedrockConverse
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI
from gen_ai_hub.proxy.native.google_genai.clients import Client as GoogleGenAIClient

from utils import settings
from utils.config import ModelConfig
from utils.logging import get_logger
from utils.models.thinking import get_openai_reasoning_effort, supports_openai_reasoning

logger = get_logger(__name__)


class OpenAIModel:
    """OpenAI Model."""

    _name: str
    _llm: ChatOpenAI

    def __init__(self, config: ModelConfig, proxy_client: BaseProxyClient):
        self._name = config.name
        extra_kwargs: dict = {}
        # reasoning_effort is only valid for reasoning-capable models (e.g. gpt-5+).
        if supports_openai_reasoning(config.name):
            reasoning_effort = get_openai_reasoning_effort(settings.THINKING_EFFORT)
            extra_kwargs["reasoning_effort"] = reasoning_effort
            logger.info(
                f"Loading OpenAI model '{config.name}' with THINKING_EFFORT={settings.THINKING_EFFORT} "
                f"(reasoning_effort='{reasoning_effort}')."
            )
        else:
            logger.info(
                f"Loading OpenAI model '{config.name}' without reasoning "
                f"(model does not support reasoning_effort)."
            )
        self._llm = ChatOpenAI(
            proxy_model_name=config.name,
            deployment_id=config.deployment_id,
            proxy_client=proxy_client,
            temperature=config.temperature,
            request_timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            **extra_kwargs,
        )

    def invoke(self, content: str):  # noqa
        """Generate content using the model"""
        response = self.llm.invoke(content)
        return response

    @property
    def name(self) -> str:
        """Returns the name of the OpenAI model."""
        return self._name

    @property
    def llm(self) -> ChatOpenAI | GoogleGenAIClient | ChatBedrockConverse:
        """Returns the instance of OpenAI model."""
        return self._llm
