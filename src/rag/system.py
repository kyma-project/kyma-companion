from typing import Protocol, cast

from langchain_core.embeddings import Embeddings
from pydantic import BaseModel

from rag.query_generator import QueryGenerator
from rag.retriever import HanaDBRetriever, Query
from utils.hana import create_hana_connection
from utils.logging import get_logger
from utils.models.factory import IModel, ModelType
from utils.settings import (
    DATABASE_PASSWORD,
    DATABASE_PORT,
    DATABASE_URL,
    DATABASE_USER,
    DOC_TABLE_NAME,
)

logger = get_logger(__name__)

class Document(BaseModel):
    """A RAG system document."""

    id: str
    content: str


class IRAGSystem(Protocol):
    """A protocol for a RAG system."""

    def query(self, query: Query) -> list[Document]:
        """Query the system with a given query."""
        ...


class RAGSystem:
    """A system that can be used to generate queries and retrieve documents."""

    def __init__(self, models: dict[str, IModel | Embeddings]):
        # setup query generator
        self.query_generator = QueryGenerator(
            cast(IModel, models[ModelType.GPT4O_MINI])
        )
        # setup retriever
        hana_conn = create_hana_connection(
            DATABASE_URL, DATABASE_PORT, DATABASE_USER, DATABASE_PASSWORD
        )
        self.retriever = HanaDBRetriever(
            embedding=cast(Embeddings, models[ModelType.TEXT_EMBEDDING_3_LARGE]),
            connection=hana_conn,
            table_name=DOC_TABLE_NAME,
        )
        
        logger.info("RAG system initialized.")
        logger.debug(f"Hana DB table name: {DOC_TABLE_NAME}")

    def retrieve(self, query: Query, top_k: int = 5) -> list[Document]:
        """Retrieve documents for a given query."""
        logger.info(f"Retrieving documents for query: {query.text}")

        alternative_queries = self.query_generator.generate_queries(query.text)
        # add original query to the list
        all_queries = [query.text] + alternative_queries.queries

        # retrieve documents for each query
        all_docs = []
        for query in all_queries:
            docs = self.retriever.retrieve(query, top_k=top_k)
            # compare the content of the new docs with the content of the existing docs
            # and add only the new ones
            new_docs = [doc for doc in docs if doc.page_content not in [doc.page_content for doc in all_docs]]
            all_docs.extend(new_docs)

        # TODO: re-rank the all_docs based on the original query

        all_docs = all_docs[:top_k]

        logger.info(f"Retrieved {len(all_docs)} documents.")
        return all_docs
