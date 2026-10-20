from enum import StrEnum

from langchain_core.embeddings import Embeddings
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from rag.system import Query, RAGSystem
from utils.models.factory import IModel
from utils.settings import RAG_TOP_K

SEARCH_KYMA_DOC_TOOL_NAME: str = "search_kyma_doc"


class DocSearchMode(StrEnum):
    """Selects the doc search backend for the search_kyma_doc tool."""

    RAG = "rag"  # default: HANA Cloud vector store over Kyma GitHub docs
    EKX = "ekx"  # experimental: SAP Enterprise Knowledge Exploration
    NULL = "null"  # experimental: no-op, always returns empty (baseline measurement)


def create_doc_search_tool(
    mode: DocSearchMode,
    models: dict[str, IModel | Embeddings],
    ekx_api_token: str = "",
) -> BaseTool:
    """Return the search_kyma_doc tool for the given mode.

    Raises ValueError when mode=ekx and ekx_api_token is empty.
    """
    from agents.kyma.tools.ekx_search import EKXSearchTool, NullSearchTool  # avoid circular import

    if mode == DocSearchMode.EKX:
        if not ekx_api_token:
            raise ValueError("EKX_API_TOKEN must be set when DOC_SEARCH_MODE=ekx")
        return EKXSearchTool(ekx_api_token=ekx_api_token)
    if mode == DocSearchMode.NULL:
        return NullSearchTool()
    return SearchKymaDocTool(models)


class SearchKymaDocArgs(BaseModel):
    """Arguments for the search_kyma_doc tool."""

    query: str = Field(
        description="The search query to find relevant Kyma documentation",
        examples=["Help me get started with kyma", "What are Kyma components?"],
    )


class SearchKymaDocTool(BaseTool):
    """Tool to search through Kyma documentation."""

    name: str = SEARCH_KYMA_DOC_TOOL_NAME
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
    top_k: int | None = Field(default=RAG_TOP_K, exclude=True)

    def __init__(self, models: dict[str, IModel | Embeddings], top_k: int = RAG_TOP_K):
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
        """Async implementation of the search through Kyma documentation. Returns concatenated content."""
        contents = await self.arun_list(query)
        combined = "\n\n -- next document -- \n\n".join(content for content in contents if content.strip())
        if not combined.strip():
            return "No relevant documentation found."
        return combined

    async def arun_list(self, query: str, top_k: int | None = None) -> list[str]:
        """Async implementation of the search through Kyma documentation. Returns list of document contents."""
        query_obj = Query(text=query)
        relevant_docs = await self.rag_system.aretrieve(
            query_obj,
            top_k=top_k if top_k is not None else (self.top_k or RAG_TOP_K),
        )
        return [doc.page_content for doc in relevant_docs if doc.page_content.strip()]
