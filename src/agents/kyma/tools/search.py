from langchain_core.embeddings import Embeddings
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import BaseTool

from rag.retriever import Query
from rag.system import RAGSystem
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

    # Add these fields
    rag_system: RAGSystem | None = Field(default=None, exclude=True)
    top_k: int | None = Field(default=5, exclude=True)

    def __init__(self, models: dict[str, IModel | Embeddings], top_k: int = 5):
        super().__init__()
        self.rag_system = RAGSystem(models)
        self.top_k = top_k

    def _run(
        self,
        query: str,
    ) -> str:
        """Execute the search through Kyma documentation."""
        query_obj = Query(text=query)
        docs = self.rag_system.retrieve(query_obj, top_k=self.top_k)

        if len(docs) == 0:
            return "No relevant documentation found for your query."

        # Format the results with source information if available
        formatted_docs = []
        for doc in docs:
            content = doc.page_content
            metadata = doc.metadata or {}
            source = metadata.get("source", "")
            if source:
                content = f"{content}\nSource: {source}"
            formatted_docs.append(content)

        docs_str = "\n\n---\n\n".join(formatted_docs)
        return docs_str

    async def _arun(self, query: str) -> str:
        """Async implementation of the search through Kyma documentation."""
        # For now, just call the sync version
        return self._run(query)
