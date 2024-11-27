from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI
from gen_ai_hub.proxy.native.google_vertexai.clients import GenerativeModel

from utils.config import ModelConfig


class GeminiModel:
    """Gemini Model."""

    _name: str
    _model: GenerativeModel

    def __init__(self, config: ModelConfig, proxy_client: BaseProxyClient):
        self._name = config.name
        self._model = GenerativeModel(
            proxy_client=proxy_client,
            model_name=config.name,
            deployment_id=config.deployment_id,
            temperature=config.temperature,
        )

    def invoke(self, content: str):  # noqa
        """Generate content using the model"""
        content = [{"role": "user", "parts": [{"text": content}]}]
        response = self.llm.generate_content(content)
        return response

    @property
    def name(self) -> str:
        """Returns the name of the gemini model."""
        return self._name

    @property
    def llm(self) -> ChatOpenAI | GenerativeModel:
        """Returns the instance of Gemini model."""
        return self._model
