from collections.abc import Callable
from typing import Any, cast

from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
from gen_ai_hub.proxy.langchain.openai import OpenAIEmbeddings
from langchain_core.embeddings import Embeddings

# TODO: re-use the model factory parent project


def create_embedding_factory(
    embedding_creator: Callable[[str, Any], Embeddings]
) -> Callable[[str], Embeddings]:
    """Create a factory function for embedding models."""

    def factory(deployment_id: str) -> Embeddings:
        proxy_client = get_proxy_client("gen-ai-hub")
        return embedding_creator(deployment_id, proxy_client)

    return factory


# OpenAI Embeddings
def openai_embedding_creator(
    deployment_id: str, proxy_client: BaseProxyClient
) -> Embeddings:
    """Create an OpenAI embedding model."""
    llm = cast(
        Embeddings,
        OpenAIEmbeddings(
            deployment_id=deployment_id,
            proxy_client=proxy_client,
        ),
    )
    return llm
