from typing import Protocol

from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel

from rag.reranker.prompt import RERANKER_PROMPT_TEMPLATE
from rag.reranker.rrf import get_relevant_documents
from rag.reranker.utils import document_to_str
from utils.logging import get_logger
from utils.models.factory import IModel

logger = get_logger(__name__)


class RerankedDoc(BaseModel):
    """A Reranked Document with page content."""

    page_content: str


class RerankedDocs(BaseModel):
    """A list of Reranked Documents."""

    documents: list[RerankedDoc]


class IReranker(Protocol):
    """Interface for RAG rerankers."""

    async def arerank(
        self,
        docs_list: list[list[Document]],
        queries: list[str],
        input_limit: int = 10,
        output_limit: int = 4,
    ) -> list[Document]:
        """Rerank the documents based on which documents are most relevant to the given queries."""
        ...


class LLMReranker(IReranker):
    """Reranker based on a language model."""

    def __init__(self, model: IModel):
        """Initialize the reranker."""
        prompt = PromptTemplate.from_template(RERANKER_PROMPT_TEMPLATE)
        self.chain = prompt | model.llm.with_structured_output(RerankedDocs)
        logger.info("Reranker initialized")

    async def arerank(
        self,
        docs_list: list[list[Document]],
        queries: list[str],
        input_limit: int = 10,
        output_limit: int = 4,
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

        try:
            # reranking using the LLM model
            response: RerankedDocs = await self.chain.ainvoke(
                {
                    "documents": format_documents(relevant_docs),
                    "queries": format_queries(queries),
                    "limit": output_limit,
                }
            )

            # return reranked documents capped at the output limit
            reranked_docs = [
                Document(page_content=doc.page_content)
                for doc in response.documents[:output_limit]
            ]
            return reranked_docs
        except Exception as e:
            logger.error(
                f"Failed to rerank documents, return filtered documents instead: {e}"
            )
            return relevant_docs[:output_limit]


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
    return "[{}]".format(",".join(f'"{query}"' for query in queries))
