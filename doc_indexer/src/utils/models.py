import time
from collections.abc import Callable
from typing import cast

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from utils.logging import get_logger

logger = get_logger(__name__)


def create_embedding_factory(
    embedding_creator: Callable[[str], Embeddings],
) -> Callable[[str], Embeddings]:
    """Create a factory function for embedding models."""

    def factory(deployment_id: str) -> Embeddings:
        return embedding_creator(deployment_id)

    return factory


# OpenAI Embeddings
def openai_embedding_creator(deployment_id: str) -> Embeddings:
    """Create an OpenAI embedding model."""
    try:
        time.sleep(1)  # Sleep to avoid rate limiting
        llm = cast(
            Embeddings,
            OpenAIEmbeddings(
                model=deployment_id,
            ),
        )
    except Exception:
        logger.exception("Error while creating OpenAI embedding model")
        raise
    return llm
