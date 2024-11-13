from typing import Any, Protocol

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel

from rag.prompts import QUERY_GENERATOR_PROMPT_TEMPLATE
from utils import logging
from utils.models.factory import IModel

logger = logging.get_logger(__name__)


class Queries(BaseModel):
    """A list of queries."""

    queries: list[str]


class IQueryGenerator(Protocol):
    """Given a single query, generates multiple alternative queries."""

    def generate_queries(self, query: str) -> list[str]:
        """Generate multiple queries based on the input query."""
        ...


class QueryGenerator:
    """Given a single query, generates multiple alternative queries."""

    def __init__(
        self,
        model: IModel,
        prompt: ChatPromptTemplate | None = None,
        num_queries: int = 5,
    ):
        self.model = model
        self.queries_parser = PydanticOutputParser(pydantic_object=Queries)
        self.prompt = prompt or ChatPromptTemplate.from_messages(
            [
                ("system", QUERY_GENERATOR_PROMPT_TEMPLATE),
                ("user", "Original query: {query}"),
                (
                    "system",
                    "Based on the original query, generate {num_queries} alternative queries that capture different aspects and "
                    "variations of the search intent. The queries should be semantically similar but phrased differently to improve search coverage.",
                ),
            ]
        ).partial(
            num_queries=num_queries,
            format_instructions=self.queries_parser.get_format_instructions(),
        )
        self._chain = self._create_chain()

    def _create_chain(self) -> Any:
        """Create a chain with langchain."""
        return self.prompt | self.model.llm | self.queries_parser

    def _invoke_chain(self, query: str) -> Queries:
        """Invokes the chat model with created chain."""
        try:
            return self._chain.invoke({"query": query})
        except Exception:
            logger.exception("Error invoking chain")
            raise

    def generate_queries(self, query: str) -> Queries:
        """Generate multiple queries based on the input query."""
        try:
            return self._invoke_chain(query)
        except Exception:
            logger.exception("Error generating queries")
            raise
