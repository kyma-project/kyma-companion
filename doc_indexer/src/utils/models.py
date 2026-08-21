import time
from collections.abc import Callable
from functools import lru_cache
from typing import cast

from aicore import AICoreClient, OpenAIEmbeddingsAdapter
from langchain_core.embeddings import Embeddings

from utils.logging import get_logger
from utils.settings import get_embedding_model_config

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _get_aicore_client() -> AICoreClient:
    return AICoreClient()


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
    deployment IDs, then uses the AICoreClient for authentication.

    Args:
        model_name: Model name as defined in config.json (e.g., "text-embedding-3-large")

    Returns:
        Embeddings instance configured for SAP AI Core

    Raises:
        ValueError: If model not found in config or missing deployment_id
    """
    try:
        time.sleep(1)  # Sleep to avoid rate limiting

        model_config = get_embedding_model_config(model_name)
        client = _get_aicore_client()

        llm = cast(
            Embeddings,
            OpenAIEmbeddingsAdapter(
                client=client,
                deployment_id=model_config.deployment_id,
                model_name=model_name,
            ).embeddings,
        )
    except Exception:
        logger.exception("Error while creating OpenAI embedding model")
        raise
    return llm
