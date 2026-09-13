from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from utils import settings
from utils.config import ModelConfig
from utils.models._aicore import AICoreClient, make_openai_chat


class OpenAIModel:
    """OpenAI Model."""

    _name: str
    _llm: ChatOpenAI

    def __init__(self, config: ModelConfig, client: AICoreClient):
        self._name = config.name
        self._llm = make_openai_chat(
            client=client,
            deployment_id=config.deployment_id,
            model_name=config.name,
            temperature=config.temperature,
            request_timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
            timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
        )

    def invoke(self, content: str):  # noqa
        """Generate content using the model"""
        return self.llm.invoke(content)

    @property
    def name(self) -> str:
        """Returns the name of the OpenAI model."""
        return self._name

    @property
    def llm(self) -> BaseChatModel:
        """Returns the instance of OpenAI model."""
        return self._llm
