from typing import Protocol

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from rag.prompts import GENERATOR_PROMPT
from utils.logging import get_logger
from utils.models.factory import IModel

logger = get_logger(__name__)


class IGenerator(Protocol):
    """A protocol for a RAG generator."""

    def generate(self, relevant_docs: list[Document], query: str) -> str:
        """Generate a response based on the RAG chain."""
        ...


class Generator:
    """A RAG generator that generates a response based on a given query and relevant documents."""

    def __init__(self, model: IModel):
        self.model = model
        prompt = PromptTemplate.from_template(GENERATOR_PROMPT)
        self.rag_chain = prompt | self.model.llm | StrOutputParser()

    def generate(self, relevant_docs: list[Document], query: str) -> str:
        """Generate a response based on the given query and relevant documents."""
        # Convert Document objects to a list of their page_content
        docs_content = [doc.page_content for doc in relevant_docs]
        try:
            response = str(
                self.rag_chain.invoke({"context": docs_content, "query": query})
            )
        except Exception as e:
            logger.exception(f"Error generating response for query: {query}")
            raise e
        return response
