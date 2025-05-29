from typing import Any, Protocol, cast

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

from rag.prompts import (
    QUERY_GENERATOR_FOLLOWUP_PROMPT_TEMPLATE,
    QUERY_GENERATOR_PROMPT_TEMPLATE,
)
from utils import logging
from utils.chain import ainvoke_chain
from utils.models.factory import IModel

logger = logging.get_logger(__name__)


class Queries(BaseModel):
    """A list of generated queries."""

    queries: list[str]


class IQueryGenerator(Protocol):
    """Given a single query, generates multiple alternative queries."""

    async def agenerate_queries(self, query: str) -> Queries:
        """Generate multiple queries based on the input query."""
        ...


class QueryGenerator:
    """Given a single query, generates multiple alternative queries."""

    def __init__(
        self,
        model: IModel,
        prompt: ChatPromptTemplate | None = None,
        num_queries: int = 4,
    ):
        self.model = model
        # self.queries_parser = PydanticOutputParser(pydantic_object=Queries)
        self.prompt = prompt or ChatPromptTemplate.from_messages(
            [
                ("system", QUERY_GENERATOR_PROMPT_TEMPLATE),
                # TODO: messages (conversation history) will be added later here
                ("user", "Original query: {query}"),
                ("system", QUERY_GENERATOR_FOLLOWUP_PROMPT_TEMPLATE),
            ]
        ).partial(
            num_queries=num_queries,
        )
        self._chain = self._create_chain()

    def _create_chain(self) -> Any:
        """Create a chain with langchain."""
        return self.prompt | self.model.llm.with_structured_output(
            Queries, method="function_calling"
        )

    async def agenerate_queries(self, query: str) -> Queries:
        """Generate multiple queries based on the input query."""
        try:
            queries = await ainvoke_chain(
                self._chain,
                {"query": query},
            )
            return cast(Queries, queries)
        except Exception:
            logger.exception(
                "Error generating alternative queries for the query: %s",
                query,
            )
            logger.info("Returning the original query as a fallback")
            return Queries(queries=[query])
