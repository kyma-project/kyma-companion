from typing import Protocol

from langchain_core.documents import Document
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel

from rag.reranker.prompt import RERANKER_PROMPT_TEMPLATE
from rag.reranker.rrf import get_relevant_documents
from rag.reranker.utils import document_to_str
from utils.chain import ainvoke_chain
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
        - The reranker filters out irrelevant documents using the Reciprocal Rank Fusion (RRF) method
          capped at the input limit.
        - Then, it reranks the remaining documents using the LLM model capped at the output limit.

        :param docs_list: A list of lists of documents.
        :param queries: A list of queries.
        :param input_limit: The maximum number of documents to consider as an input for the LLM reranker.
        :param output_limit: The maximum number of documents to return.
        :return: A list of reranked documents.
        """
        logger.info(f"Reranking documents for queries: {queries}")
        docs = []
        try:
            docs = get_relevant_documents(docs_list, input_limit)
            if not docs:
                docs = flatten_unique(docs_list, output_limit)
            return await self._chain_ainvoke(docs, queries, output_limit)
        except Exception as e:
            logger.error(
                f"Failed to rerank documents, return top {output_limit} unique documents: {e}"
            )
            return docs[:output_limit]

    async def _chain_ainvoke(
        self, docs: list[Document], queries: list[str], limit: int
    ) -> list[Document]:
        """
        Invoke the reranker model with the relevant documents and queries.
        :param docs: A list of documents.
        :param queries: A list of queries.
        :param limit: The maximum number of documents to return.
        :return: A list of reranked documents.
        """

        # reranking using the LLM model
        response: RerankedDocs = await ainvoke_chain(
            self.chain,
            {
                "documents": format_documents(docs),
                "queries": format_queries(queries),
                "limit": limit,
            },
        )
        # return reranked documents capped at the output limit
        reranked_docs = [
            Document(page_content=doc.page_content)
            for doc in response.documents[:limit]
        ]
        return reranked_docs


def flatten_unique(docs_list: list[list[Document]], limit: int = -1) -> list[Document]:
    """
    Flatten the list of lists of documents and return the first unique documents up to the limit.
    :param docs_list: A list of lists of documents.
    :param limit: The maximum number of documents to return. If -1, return all unique documents.
    :return: A list of unique documents.
    """
    if limit == 0:
        return []
    documents: list[Document] = []
    for docs in docs_list:
        for doc in docs:
            if doc not in documents:
                documents.append(doc)
            if len(documents) == limit:
                break
        if len(documents) == limit:
            break
    return documents


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
