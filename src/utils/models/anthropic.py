from aicore import AICoreClient, AnthropicAdapter
from langchain_core.language_models import BaseChatModel

from utils.config import ModelConfig


class AnthropicModel:
    """Anthropic Claude model via AWS Bedrock Converse API."""

    _name: str
    _llm: BaseChatModel

    def __init__(self, config: ModelConfig, client: AICoreClient) -> None:
        self._name = config.name
        adapter = AnthropicAdapter(
            client=client,
            deployment_id=config.deployment_id,
            model_name=config.name,
            temperature=config.temperature,
        )
        self._llm = adapter.llm

    def invoke(self, content: str):  # noqa
        """Generate content using the model."""
        return self._llm.invoke(content)

    @property
    def name(self) -> str:
        """Returns the name of the Anthropic model."""
        return self._name

    @property
    def llm(self) -> BaseChatModel:
        """Returns the instance of the Anthropic model."""
        return self._llm
