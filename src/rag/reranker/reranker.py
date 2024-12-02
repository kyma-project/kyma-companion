import json
from typing import Protocol

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from rag.reranker.prompt import RERANKER_PROMPT_TEMPLATE
from rag.reranker.rrf import get_relevant_documents
from rag.reranker.utils import document_to_str, dict_to_document
from utils.logging import get_logger
from utils.models.factory import IModel

logger = get_logger(__name__)


class IReranker(Protocol):
    """Interface for RAG rerankers."""

    def rerank(
            self, docs_list: list[list[Document]], queries: list[str], input_limit: int = 10, output_limit: int = 4
    ) -> list[Document]:
        """Rerank the documents based on which documents are most relevant to the given queries."""
        ...


class LLMReranker(IReranker):
    """Reranker based on a language model."""

    def __init__(self, model: IModel):
        """Initialize the reranker."""
        prompt = PromptTemplate.from_template(RERANKER_PROMPT_TEMPLATE)
        self.chain = prompt | model.llm | StrOutputParser()

    def rerank(
            self, docs_list: list[list[Document]], queries: list[str], input_limit: int = 10, output_limit: int = 4
    ) -> list[Document]:
        """
        Rerank the documents based on which documents are most relevant to the given queries.
        The documents are first filtered based on their relevance to the queries and capped at the input limit.
        Then, the LLM reranker is used to rerank the filtered documents and capped at the output limit.
        Finally, the reranked documents are returned.
        :param docs_list: A list of lists of documents.
        :param queries: A list of queries.
        :param input_limit: The maximum number of documents to consider for reranking.
        :param output_limit: The maximum number of documents to return.
        :return: A list of reranked documents.
        """
        logger.info(f"Reranking documents for queries: {queries}")

        # filtration to prevent reranking irrelevant documents
        relevant_docs = get_relevant_documents(docs_list, limit=input_limit)

        # reranking using the LLM model
        response = self.chain.invoke(
            {
                "documents": format_documents(relevant_docs),
                "queries": format_queries(queries),
                "limit": output_limit,
            }
        )

        # parsing the response from the LLM model
        ranked_docs = parse_response(response)
        return ranked_docs


def format_documents(docs: list[Document]) -> str:
    """
    Format the documents for the prompt.
    :param docs: A list of documents.
    :return: A string representation of the documents in JSON format.
    """
    return "[{}]".format(",".join(document_to_str(doc) for doc in docs))


def format_queries(queries: list[str]) -> str:
    """
    Format the queries for the prompt.
    :param queries: A list of queries.
    :return: A string representation of the queries in JSON format.
    """
    return "[{}]".format(",".join("\"{}\"".format(query) for query in queries))


def parse_response(response: str) -> list[Document]:
    """
    Parse the response from the reranker.
    :param response: The response from the reranker.
    :return: A list of documents.
    """
    response = response.strip('`').lstrip('json').strip()
    return [dict_to_document(obj) for obj in json.loads(response)]
