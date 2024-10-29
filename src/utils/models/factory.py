from collections.abc import Callable
from enum import Enum
from functools import lru_cache
from typing import Any, Protocol, cast

from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI, OpenAIEmbeddings
from gen_ai_hub.proxy.native.google_vertexai.clients import GenerativeModel
from langchain_core.embeddings import Embeddings

from utils.config import ModelConfig, get_config
from utils.models.exceptions import ModelNotFoundError, UnsupportedModelError
from utils.models.gemini import GeminiModel
from utils.models.openai import OpenAIModel


class ModelPrefix:
    GPT = "gpt"
    GEMINI = "gemini"
    TEXT_EMBEDDING = "text-embedding"


class EmbeddingModelPrefix:
    OPENAI = "text-embedding"
    GECKO = "textembedding-gecko"


class ModelType(str, Enum):
    """Enum for LLM model names."""

    GPT4O = "gpt-4o"
    GPT4O_MINI = "gpt-4o-mini"
    GPT35 = "gpt-3.5"
    GEMINI_10_PRO = "gemini-1.0-pro"
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"


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


@lru_cache(maxsize=1)
def init_proxy_client() -> BaseProxyClient:
    """Initialize the proxy client for the GenAI Hub only once."""
    return get_proxy_client("gen-ai-hub")


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

class IModelFactory(Protocol):
    """Model Factory Interface."""

    def create_model(self, name: str) -> IModel | Embeddings:
        """Create a model."""
        ...

    def create_models(self) -> dict[str, IModel | Embeddings]:
        """Create all models."""
        ...


class ModelFactory:
    """Model Factory for LLM and Embedding models."""

    def __init__(self):
        self._proxy_client = init_proxy_client()
        self._models: dict[str, IModel] = {}

    def create_model(self, name: str) -> IModel | Embeddings:
        """
        Create a model for the given name.
        """
        # TODO: Maybe use deployment ID as a key in addition to the model name.
        model: IModel | None = self._models.get(name)
        if model:
            return model

        model_config = get_model_config(name)
        if model_config is None:
            raise ModelNotFoundError(f"Model {name} not found in the configuration.")

        if name.startswith(ModelPrefix.GPT):
            model = OpenAIModel(model_config, self._proxy_client)
        elif name.startswith(ModelPrefix.GEMINI):
            model = GeminiModel(model_config, self._proxy_client)
        elif name.startswith(ModelPrefix.TEXT_EMBEDDING):
            model = cast(
                Embeddings,
                OpenAIEmbeddings(
                    model=name,
                    deployment_id=model_config.deployment_id,
                    proxy_client=self._proxy_client,
                ),
            )
        else:
            raise UnsupportedModelError(f"Model {name} not supported.")
        # add to cache
        self._models[name] = model
        return model

    def create_models(self) -> dict[str, IModel | Embeddings]:
        """Create all models defined in the configuration."""
        return {
            model.name: self.create_model(model.name) for model in get_config().models
        }
