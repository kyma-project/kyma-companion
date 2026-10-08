"""Client for the remote kyma-docs-search service."""

import aiohttp
from langchain_core.documents import Document

from rag.system import Query
from utils.logging import get_logger

logger = get_logger(__name__)


class RemoteRAGSystem:
    """A RAG system that delegates retrieval to the kyma-docs-search HTTP service."""

    def __init__(self, base_url: str, timeout_seconds: float = 60):
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async def aretrieve(self, query: Query, top_k: int = 5) -> list[Document]:
        """Retrieve documents for a given query from the remote service."""
        payload = {"query": query.text, "top_k": top_k, "expand_queries": True, "rerank": True}
        data = await self._request("POST", "/v1/search", json=payload)
        logger.debug(
            f"Remote docs search: queries={data.get('queries')}, score_type={data.get('score_type')}, "
            f"run_id={(data.get('index') or {}).get('run_id')}"
        )
        return [
            Document(page_content=result["content"], metadata=result["metadata"]) for result in data.get("results", [])
        ]

    async def status(self) -> dict:
        """Return the index status of the remote service (GET /v1/status)."""
        return await self._request("GET", "/v1/status")

    async def _request(self, method: str, path: str, json: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        try:
            async with (
                aiohttp.ClientSession(timeout=self.timeout) as session,
                session.request(method, url, json=json) as response,
            ):
                if not response.ok:
                    body = await response.text()
                    logger.error(f"Remote docs search {method} {url} failed with {response.status}: {body}")
                    response.raise_for_status()
                result: dict = await response.json()
                return result
        except aiohttp.ClientError:
            logger.exception(f"Remote docs search request {method} {url} failed.")
            raise
