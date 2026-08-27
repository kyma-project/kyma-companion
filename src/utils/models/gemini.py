from google.genai import Client as GoogleGenAIClient
from langchain_core.language_models import BaseChatModel

from utils.config import ModelConfig
from utils.models._aicore import AICoreClient, make_gemini_client


class GeminiModel:
    """Gemini Model."""

    _name: str
    _model: GoogleGenAIClient

    def __init__(self, config: ModelConfig, client: AICoreClient):
        self._name = config.name
        self._model = make_gemini_client(client=client, deployment_id=config.deployment_id)

    def invoke(self, content: str):  # noqa
        """Generate content using the model"""
        return self._model.models.generate_content(model=self._name, contents=content)

    @property
    def name(self) -> str:
        """Returns the name of the gemini model."""
        return self._name

    @property
    def llm(self) -> BaseChatModel:
        """Returns the instance of Gemini model."""
        raise NotImplementedError("GeminiModel does not expose a BaseChatModel; use invoke() directly.")
