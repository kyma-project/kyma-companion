from typing import Protocol

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from rag.prompts import GENERATOR_PROMPT
from utils.chain import ainvoke_chain
from utils.logging import get_logger
from utils.models.factory import IModel

logger = get_logger(__name__)


class IGenerator(Protocol):
    """A protocol for a RAG generator."""

    async def generate(self, relevant_docs: list[Document], query: str) -> str:
        """Generate a response based on the RAG chain."""
        ...


class Generator:
    """A RAG generator that generates a response based on a given query and relevant documents."""

    def __init__(self, model: IModel):
        self.model = model
        prompt = PromptTemplate.from_template(GENERATOR_PROMPT)
        self.rag_chain = prompt | self.model.llm | StrOutputParser()

    async def agenerate(self, relevant_docs: list[Document], query: str) -> str:
        """Generate a response based on the given query and relevant documents."""
        """Generate a response based on the RAG chain."""
        # Convert Document objects to a list of their page_content
        docs_content = "\n\n".join(doc.page_content for doc in relevant_docs)
        if not docs_content.strip():
            return """I'm sorry, but I couldn't find any relevant documents in the knowledge base 
            that match your query at this time. 
            It's possible that the specific information you're looking 
            for isn't currently indexed or available in the system. 
            You might consider rephrasing your query with different 
            keywords or providing more context so I can try again."""
        try:
            response = await ainvoke_chain(
                self.rag_chain,
                {"context": docs_content, "query": query},
            )
        except Exception as e:
            logger.exception(f"Error generating response for query: {query}")
            raise e
        return str(response)
