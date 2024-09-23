from enum import Enum
from typing import Protocol

from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI
from gen_ai_hub.proxy.native.google_vertexai.clients import GenerativeModel

from utils.config import ModelConfig, get_config


class LLM(str, Enum):
    """Enum for LLM model names."""

    GPT4O = "gpt-4o"
    GPT4O_MINI = "gpt-4o-mini"
    GPT35 = "gpt-3.5"
    GEMINI_10_PRO = "gemini-1.0-pro"


class IModel(Protocol):
    """Model Interface."""

    def invoke(self, content: str):  # noqa
        """
        Args:
            content:  query to generate content

        Returns:
            str: The generated content

        """

    @property
    def name(self) -> str:
        """The name of the model."""
        ...

    """The name of the model."""

    @property
    def llm(self) -> ChatOpenAI | GenerativeModel:
        """The instance of the model."""
        ...


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


def get_model_config(name: str) -> ModelConfig | None:
    """
    Retrieve a model data by its name.

    Args:
        name (str): The name of the model to find.

    Returns:
        ModelConfig | None: The matching model if found, otherwise None.
    """
    config = get_config()
    return next((model for model in config.models if model.name == name), None)


class ModelFactory:
    """Model Factory."""

    _models: dict[str, IModel] = {}
    _proxy_client: BaseProxyClient

    def __init__(self):
        self._proxy_client = get_proxy_client("gen-ai-hub")

    def create_model(self, name: str, temperature: int = 0) -> IModel:
        """
        Create a ChatOpenAI instance.
        """
        model_config = get_model_config(name)
        if model_config is None:
            raise ValueError(f"Model {name} not found in the configuration.")

        model: IModel
        if model_config.name.startswith("gpt"):
            model = OpenAIModel(model_config, self._proxy_client)
        else:
            model = GeminiModel(model_config, self._proxy_client)
        self._models[name] = model
        return model

    def get_model(self, name: str) -> IModel | None:
        """
        Get a ChatOpenAI instance.
        """
        return self._models.get(name)
