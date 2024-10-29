
from collections.abc import Callable
import logging
from typing import Any, cast

from gen_ai_hub.proxy.core.base import BaseProxyClient
from gen_ai_hub.proxy.core.proxy_clients import get_proxy_client
from gen_ai_hub.proxy.langchain.openai import OpenAIEmbeddings
from hdbcli import dbapi
from langchain_community.vectorstores import HanaDB
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

def create_hana_connection(
    url: str, port: int, user: str, password: str
) -> dbapi.Connection | None:
    """Create a connection to the Hana Cloud DB."""
    try:
        connection = dbapi.connect(
            address=url,
            port=port,
            user=user,
            password=password,
        )
        return connection
    except dbapi.Error:
        logging.exception("Connection to Hana Cloud failed.")
    except Exception:
        logging.exception("Unknown error occurred.")
    return None

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


class Retriever:
    def __init__(
        self, embedding: Embeddings, connection: dbapi.Connection, table_name: str
    ):
        self.db = HanaDB(
            connection=connection,
            embedding=embedding,
            table_name=table_name,
        )

    def retrieve(self, query: str) -> list[Document]:
        docs = self.db.similarity_search(query, k=3)
        return docs
