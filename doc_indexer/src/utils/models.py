import time
from collections.abc import Callable
from functools import lru_cache
from typing import Any, cast

from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
from gen_ai_hub.proxy.langchain.openai import OpenAIEmbeddings
from langchain_core.embeddings import Embeddings

from utils.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def init_proxy_client() -> BaseProxyClient:
    """Initialize the proxy client."""
    try:
        return get_proxy_client("gen-ai-hub")
    except Exception:
        logger.exception("Error while initializing proxy client")
        raise


def create_embedding_factory(
    embedding_creator: Callable[[str, Any], Embeddings],
) -> Callable[[str], Embeddings]:
    """Create a factory function for embedding models."""

    def factory(deployment_id: str) -> Embeddings:
        proxy_client = init_proxy_client()
        return embedding_creator(deployment_id, proxy_client)

    return factory


# OpenAI Embeddings
def openai_embedding_creator(
    deployment_id: str, proxy_client: BaseProxyClient
) -> Embeddings:
    """Create an OpenAI embedding model."""
    try:
        # time.sleep(1)  # Sleep to avoid rate limiting
        llm = cast(
            Embeddings,
            OpenAIEmbeddings(
                deployment_id=deployment_id,
                proxy_client=proxy_client,
            ),
        )
    except Exception:
        logger.exception("Error while creating OpenAI embedding model")
        raise
    return llm
