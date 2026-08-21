from aicore import AICoreClient, GeminiAdapter
from google.genai import Client as GoogleGenAIClient

from utils.config import ModelConfig


class GeminiModel:
    """Gemini Model -- uses google.genai.Client directly, not a LangChain BaseChatModel."""

    _name: str
    _model: GoogleGenAIClient

    def __init__(self, config: ModelConfig, client: AICoreClient) -> None:
        self._name = config.name
        adapter = GeminiAdapter(client=client, deployment_id=config.deployment_id)
        self._model = adapter.llm

    def invoke(self, content: str):  # noqa
        """Generate content using the model"""
        return self._model.models.generate_content(
            model=self._name,
            contents=content,
        )

    @property
    def name(self) -> str:
        """Returns the name of the gemini model."""
        return self._name

    @property
    def llm(self) -> GoogleGenAIClient:
        """Returns the underlying google.genai.Client instance."""
        return self._model
