from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI
from gen_ai_hub.proxy.native.google_genai.clients import Client as GoogleGenAIClient

from utils.config import ModelConfig


class GeminiModel:
    """Gemini Model."""

    _name: str
    _model: GoogleGenAIClient

    def __init__(self, config: ModelConfig, proxy_client: BaseProxyClient):
        self._name = config.name
        self._model = GoogleGenAIClient(
            proxy_client=proxy_client,
            deployment_id=config.deployment_id,
        )

    def invoke(self, content: str):  # noqa
        """Generate content using the model"""
        response = self._model.models.generate_content(
            model=self._name,
            contents=content,
        )
        return response

    @property
    def name(self) -> str:
        """Returns the name of the gemini model."""
        return self._name

    @property
    def llm(self) -> ChatOpenAI | GoogleGenAIClient:
        """Returns the instance of Gemini model."""
        return self._model
