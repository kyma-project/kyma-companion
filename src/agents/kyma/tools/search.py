from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from rag.system import Query, RAGSystem
from utils.models.factory import IModel

DEFAULT_TOP_K: int = 5
SEARCH_KYMA_DOC_TOOL_NAME: str = "search_kyma_doc"


class SearchKymaDocArgs(BaseModel):
    """Arguments for the search_kyma_doc tool."""

    query: str = Field(
        description="The search query to find relevant Kyma documentation",
        examples=["Help me get started with kyma", "What are Kyma components?"],
    )


def _format_document(doc: Document) -> str:
    """Format a single Document into a human-readable block with title and source URL.

    Args:
        doc: A LangChain Document with page_content and optional metadata fields
             (title, url, source, module).

    Returns:
        Formatted string block for the document.
    """
    title = doc.metadata.get("title") or "Untitled"
    url = doc.metadata.get("url") or doc.metadata.get("source") or ""
    module = doc.metadata.get("module") or ""

    lines = [f"### {title}"]
    if url:
        lines.append(f"Source: {url}")
    if module:
        lines.append(f"Module: {module}")
    lines.append("")
    lines.append(doc.page_content)
    return "\n".join(lines)


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
    top_k: int | None = Field(default=DEFAULT_TOP_K, exclude=True)

    def __init__(self, models: dict[str, IModel | Embeddings], top_k: int = DEFAULT_TOP_K):
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
        """Async implementation of the search through Kyma documentation.

        Returns documents formatted with title, source URL, module, and content,
        separated by horizontal rules.
        """
        docs = await self.arun_documents(query)
        if not docs:
            return "No relevant documentation found."
        formatted = [_format_document(doc) for doc in docs]
        return "\n\n---\n\n".join(formatted)

    async def arun_documents(self, query: str, top_k: int | None = None) -> list[Document]:
        """Retrieve raw Document objects with metadata for the given query.

        Args:
            query: The search query string.
            top_k: Maximum number of documents to return. Falls back to the
                   instance default when not provided.

        Returns:
            List of Document objects with page_content and metadata (title, url, module).
        """
        if self.rag_system is None:
            return []
        query_obj = Query(text=query)
        relevant_docs = await self.rag_system.aretrieve(
            query_obj,
            top_k=top_k if top_k is not None else (self.top_k or DEFAULT_TOP_K),
        )
        return [doc for doc in relevant_docs if doc.page_content.strip()]

    async def arun_list(self, query: str, top_k: int | None = None) -> list[str]:
        """Retrieve document content strings for the given query.

        Kept for backward compatibility with the REST endpoint and existing
        callers. Implemented on top of ``arun_documents``.

        Args:
            query: The search query string.
            top_k: Maximum number of documents to return.

        Returns:
            List of page_content strings for matched documents.
        """
        docs = await self.arun_documents(query, top_k=top_k)
        return [doc.page_content for doc in docs]
