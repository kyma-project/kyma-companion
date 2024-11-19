from textwrap import dedent
from typing import Protocol

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from utils.models.factory import IModel


class IGenerator(Protocol):
    """A protocol for a RAG generator."""

    def generate(self, docs: list[str], query: str) -> str:
        """Generate a response based on the RAG chain."""
        ...


class Generator:
    """A generator that can be used to generate documents based on a given query."""

    def __init__(self, model: IModel):
        self.model = model
        prompt = PromptTemplate.from_template(
            dedent(
                """
                You are Kyma documentation assistant who helps to retrieve the information from Kyma documentation. 
                Use the following pieces of retrieved context to answer the query.
                Answer the specific question directly.
                Include only information from the provided context.
                If you don't know the answer, just say that you don't know.
                
                Query: {query} 

                Context: {context} 

                Answer:
                """
            )
        )
        self.rag_chain = prompt | self.model.llm | StrOutputParser()

    def generate(self, relevant_docs: list[Document], query: str) -> str:
        """Generate a response based on the RAG chain."""
        # Convert Document objects to a list of their page_content
        docs_content = [doc.page_content for doc in relevant_docs]

        response = str(self.rag_chain.invoke({"context": docs_content, "query": query}))
        return response
