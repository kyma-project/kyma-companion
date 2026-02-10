from enum import Enum
from functools import lru_cache
from typing import Protocol, cast, runtime_checkable

from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI, OpenAIEmbeddings
from gen_ai_hub.proxy.native.google_genai.clients import Client as GoogleGenAIClient
from langchain_core.embeddings import Embeddings

from utils.config import Config
from utils.models.exceptions import ModelNotFoundError, UnsupportedModelError
from utils.models.gemini import GeminiModel
from utils.models.openai import OpenAIModel


class ModelPrefix:
    """Model Prefixes."""

    GPT = "gpt"
    GEMINI = "gemini"
    TEXT_EMBEDDING = "text-embedding"


class EmbeddingModelPrefix:
    """Embedding Model Prefixes."""

    OPENAI = "text-embedding"
    GECKO = "textembedding-gecko"


class ModelType(str, Enum):
    """Enum for LLM model names."""

    GPT41 = "gpt-4.1"
    GPT41_MINI = "gpt-4.1-mini"
    TEXT_EMBEDDING_3_LARGE = "text-embedding-3-large"


@runtime_checkable
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
    def llm(self) -> ChatOpenAI | GoogleGenAIClient:
        """The instance of the model."""
        ...


@lru_cache(maxsize=1)
def init_proxy_client() -> BaseProxyClient:
    """Initialize the proxy client for the GenAI Hub only once."""
    return get_proxy_client("gen-ai-hub")


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

    def __init__(self, config: Config):
        self._proxy_client = init_proxy_client()
        self._models: dict[str, IModel | Embeddings] = {}
        self._config = config

    def create_model(self, name: str) -> IModel | Embeddings:
        """
        Create a model for the given name.
        """
        # Check cache.
        if name in self._models:
            return self._models[name]

        # Build a lookup table for model configurations.
        model_config_map = {model.name: model for model in self._config.models}
        model_config = model_config_map.get(name)

        if model_config is None:
            raise ModelNotFoundError(f"Model '{name}' not found in the configuration.")

        # Dispatch mechanism for model creation.
        model_prefix_dispatch = {
            ModelPrefix.GPT: lambda: OpenAIModel(model_config, self._proxy_client),
            ModelPrefix.GEMINI: lambda: GeminiModel(model_config, self._proxy_client),
            ModelPrefix.TEXT_EMBEDDING: lambda: cast(
                Embeddings,
                OpenAIEmbeddings(
                    model=name,
                    deployment_id=model_config.deployment_id,
                    proxy_client=self._proxy_client,
                ),
            ),
        }

        # Check if the model name starts with any of the prefixes.
        for prefix, create_fn in model_prefix_dispatch.items():
            if name.startswith(prefix):
                model = create_fn()
                # Cache the model.
                self._models[name] = cast(IModel | Embeddings, model)
                return cast(IModel | Embeddings, model)

        raise UnsupportedModelError(f"Model '{name}' is not supported.")

    def create_models(self) -> dict[str, IModel | Embeddings]:
        """Create all models defined in the configuration."""
        return {model.name: self.create_model(model.name) for model in self._config.models}
