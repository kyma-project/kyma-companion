from aicore import AICoreClient, OpenAIAdapter
from langchain_core.language_models import BaseChatModel

from utils import settings
from utils.config import ModelConfig


class OpenAIModel:
    """OpenAI Model."""

    _name: str
    _llm: BaseChatModel

    def __init__(self, config: ModelConfig, client: AICoreClient) -> None:
        self._name = config.name
        adapter = OpenAIAdapter(
            client=client,
            deployment_id=config.deployment_id,
            model_name=config.name,
            temperature=config.temperature,
            request_timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
        )
        self._llm = adapter.llm

    def invoke(self, content: str):  # noqa
        """Generate content using the model"""
        return self._llm.invoke(content)

    @property
    def name(self) -> str:
        """Returns the name of the OpenAI model."""
        return self._name

    @property
    def llm(self) -> BaseChatModel:
        """Returns the instance of OpenAI model."""
        return self._llm
