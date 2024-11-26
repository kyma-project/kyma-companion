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
    """TODO(marcobebway)"""

    def rerank(
            self, docs: list[Document], queries: list[str], input_limit=10, output_limit: int = 4
    ) -> list[Document]:
        """TODO(marcobebway)"""
        ...


class LLMReranker(IReranker):
    """TODO(marcobebway)"""

    def __init__(self, model: IModel):
        """TODO(marcobebway)"""
        prompt = PromptTemplate.from_template(RERANKER_PROMPT_TEMPLATE)
        self.chain = prompt | model.llm | StrOutputParser()

    def rerank(
            self, docs: list[Document], queries: list[str], input_limit=10, output_limit: int = 4
    ) -> list[Document]:
        """TODO(marcobebway)"""
        logger.info(f"Reranking {len(docs)} documents for queries: {queries}")

        # filtration
        relevant_docs = get_relevant_documents(docs, limit=input_limit)

        # reranking
        response = self.chain.invoke(
            {
                "documents": format_documents(relevant_docs),
                "queries": format_queries(queries),
                "limit": output_limit,
            }
        )

        # response
        ranked_docs = parse_response(response)
        return ranked_docs


def format_documents(docs: list[Document]) -> str:
    """TODO(marcobebway)"""
    return "[{}]".format(",".join(document_to_str(doc) for doc in docs))


def format_queries(queries: list[str]) -> str:
    """TODO(marcobebway)"""
    return "[{}]".format(",".join("\"{}\"".format(query) for query in queries))


def parse_response(response: str) -> list[Document]:
    """TODO(marcobebway)"""
    response = response.strip('`').lstrip('json').strip()
    return [dict_to_document(obj) for obj in json.loads(response)]
