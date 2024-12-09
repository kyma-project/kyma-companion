from langchain_core.embeddings import Embeddings
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

from rag.system import Query, RAGSystem
from utils.models.factory import IModel


class SearchKymaDocArgs(BaseModel):
    """Arguments for the search_kyma_doc tool."""

    query: str = Field(
        description="The search query to find relevant Kyma documentation",
        examples=["How to install Kyma?", "What are Kyma components?"],
    )


class SearchKymaDocTool(BaseTool):
    """Tool to search through Kyma documentation."""

    name: str = "search_kyma_doc"
    description: str = """Used to search through Kyma documentation for relevant information about Kyma concepts, 
    features, components, resources, or troubleshooting. A query is required to search the documentation.

    Example queries:
    - "How do I install Kyma?"
    - "What are the main Kyma components?"
    - "How to troubleshoot Kyma Istio module?"
    """

    args_schema: type[BaseModel] = SearchKymaDocArgs
    return_direct: bool = False  # Let the agent process the search results

    # the following fields are not part of the schema, but are used internally
    rag_system: RAGSystem | None = Field(default=None, exclude=True)
    top_k: int | None = Field(default=5, exclude=True)

    def __init__(self, models: dict[str, IModel | Embeddings], top_k: int = 4):
        super().__init__()
        self.rag_system = RAGSystem(models)
        self.top_k = top_k

    def _run(
        self,
        query: str,
    ) -> str:
        """Execute the search through Kyma documentation."""
        return ""

    async def _arun(self, query: str) -> str:
        """Async implementation of the search through Kyma documentation."""
        # For now, just call the sync version
        query_obj = Query(text=query)
        relevant_docs = await self.rag_system.aretrieve(query_obj)
        rag_response = await self.rag_system.agenerate(query_obj, relevant_docs)
        return rag_response
