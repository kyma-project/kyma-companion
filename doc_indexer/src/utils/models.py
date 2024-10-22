from typing import Callable, Any

from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
from gen_ai_hub.proxy.langchain.openai import OpenAIEmbeddings
from langchain_core.embeddings import Embeddings


def create_embedding_factory(
    embedding_creator: Callable[[str, Any], Embeddings]
) -> Callable[[str], Embeddings]:

    def factory(deployment_id: str) -> Embeddings:
        proxy_client = get_proxy_client("gen-ai-hub")
        return embedding_creator(deployment_id, proxy_client)

    return factory


# OpenAI Embeddings
def create_openai_embeddings(
    deployment_id: str, proxy_client: BaseProxyClient
) -> Embeddings:
    llm = OpenAIEmbeddings(
        deployment_id=deployment_id,
        proxy_client=proxy_client,
    )
    return llm


create_openai_embedding = create_embedding_factory(create_openai_embeddings)
