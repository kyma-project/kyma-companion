from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI
from gen_ai_hub.proxy.native.google_vertexai.clients import GenerativeModel

from utils.config import ModelConfig


class OpenAIModel:
    """OpenAI Model."""

    _name: str
    _llm: ChatOpenAI

    def __init__(self, config: ModelConfig, proxy_client: BaseProxyClient):
        self._name = config.name
        self._llm = ChatOpenAI(
            deployment_id=config.deployment_id,
            proxy_client=proxy_client,
            temperature=config.temperature,
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
    def llm(self) -> ChatOpenAI | GenerativeModel:
        """Returns the instance of OpenAI model."""
        return self._llm
    
