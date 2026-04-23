import time
from collections.abc import Callable
from typing import cast

from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
from gen_ai_hub.proxy.langchain import OpenAIEmbeddings
from langchain_core.embeddings import Embeddings

from utils.logging import get_logger
from utils.settings import get_embedding_model_config

logger = get_logger(__name__)


class FastEmbedEmbeddings(Embeddings):
    """Langchain-compatible wrapper around fastembed.TextEmbedding."""

    def __init__(self, model_name: str, threads: int = 2):
        # imported lazily so fastembed is only required when INDEX_TO_FILE=true
        from fastembed import TextEmbedding

        # threads limits ONNX Runtime intra-op threads to reduce peak memory
        self._model = TextEmbedding(model_name, threads=threads)

    def embed_documents(self, texts: list[str], batch_size: int = 8) -> list[list[float]]:
        """Embed a list of documents into vectors."""
        result: list[list[float]] = [v.tolist() for v in self._model.embed(texts, batch_size=batch_size)]
        return result

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string into a vector."""
        result: list[float] = list(self._model.embed([text]))[0].tolist()
        return result


def fastembed_embedding_creator(model_name: str) -> FastEmbedEmbeddings:
    """Create a local fastembed embedding model (no external API required.)"""
    return FastEmbedEmbeddings(model_name)


def create_embedding_factory(
    embedding_creator: Callable[[str], Embeddings],
) -> Callable[[str], Embeddings]:
    """Create a factory function for embedding models."""

    def factory(model_name: str) -> Embeddings:
        return embedding_creator(model_name)

    return factory


def openai_embedding_creator(model_name: str) -> Embeddings:
    """Create an OpenAI embedding model using SAP AI Core.

    Reads model configuration from settings to map model names to SAP AI Core
    deployment IDs, then uses the gen_ai_hub proxy for authentication.

    Args:
        model_name: Model name as defined in config.json (e.g., "text-embedding-3-large")

    Returns:
        Embeddings instance configured for SAP AI Core

    Raises:
        ValueError: If model not found in config or missing deployment_id
    """
    try:
        time.sleep(1)  # Sleep to avoid rate limiting

        # Look up deployment_id from settings
        model_config = get_embedding_model_config(model_name)

        # Initialize SAP AI Core proxy client
        proxy_client = get_proxy_client("gen-ai-hub")

        # Create embeddings with model name and deployment_id
        llm = cast(
            Embeddings,
            OpenAIEmbeddings(
                model=model_name,
                deployment_id=model_config.deployment_id,
                proxy_client=proxy_client,
            ),
        )
    except Exception:
        logger.exception("Error while creating OpenAI embedding model")
        raise
    return llm
