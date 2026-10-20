# EXPERIMENTAL: EKX-backed and null implementations of search_kyma_doc.
#
# Not part of the production search path. Activated via DOC_SEARCH_MODE setting.

import json
import uuid

import httpx
from langchain_core.tools import BaseTool
from pydantic import BaseModel

from agents.kyma.tools.search import SEARCH_KYMA_DOC_TOOL_NAME, SearchKymaDocArgs
from utils.logging import get_logger

logger = get_logger(__name__)

EKX_STREAM_URL = "https://ekx.cloud.sap/api/chat/stream"

# Timeout for the full EKX streaming response (EKX does multi-step SPARQL).
_EKX_TIMEOUT_SECONDS = 60

_TOOL_DESCRIPTION = """Used to search through Kyma documentation for relevant information about Kyma concepts,
    features, components, resources, or troubleshooting. A query is required to search the documentation.

    Example queries:
    - "How do I install Kyma?"
    - "What are the main Kyma components?"
    - "How to troubleshoot Kyma Istio module?"
    """


class EKXSearchTool(BaseTool):
    """EXPERIMENTAL search_kyma_doc backed by SAP Enterprise Knowledge Exploration (EKX).

    Calls POST ekx.cloud.sap/api/chat/stream and returns the final ai_message
    from the NDJSON stream. Activate with DOC_SEARCH_MODE=ekx.
    """

    name: str = SEARCH_KYMA_DOC_TOOL_NAME
    description: str = _TOOL_DESCRIPTION
    args_schema: type[BaseModel] = SearchKymaDocArgs
    return_direct: bool = False

    ekx_api_token: str

    def __init__(self, ekx_api_token: str) -> None:
        super().__init__(ekx_api_token=ekx_api_token)

    def _run(self, query: str) -> str:
        return ""

    async def _arun(self, query: str) -> str:
        """Call EKX and return the final AI answer."""
        thread_id = str(uuid.uuid4())
        payload = {"query": query, "threadId": thread_id, "mode_id": "normal"}

        try:
            async with (
                httpx.AsyncClient(timeout=_EKX_TIMEOUT_SECONDS) as client,
                client.stream(
                    "POST",
                    EKX_STREAM_URL,
                    headers={
                        "Authorization": f"Bearer {self.ekx_api_token}",
                        "Content-Type": "application/json",
                    },
                    content=json.dumps(payload),
                ) as resp,
            ):
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "ai_message" and event.get("is_final", True):
                        return str(event.get("content", ""))
        except Exception:
            logger.exception("EKX search failed for query=%r", query)

        return "No relevant documentation found."


class NullSearchTool(BaseTool):
    """EXPERIMENTAL search_kyma_doc that always returns empty string.

    Measures how much the doc search tool contributes to answer quality.
    Activate with DOC_SEARCH_MODE=null.
    """

    name: str = SEARCH_KYMA_DOC_TOOL_NAME
    description: str = _TOOL_DESCRIPTION
    args_schema: type[BaseModel] = SearchKymaDocArgs
    return_direct: bool = False

    def _run(self, query: str) -> str:
        return ""

    async def _arun(self, query: str) -> str:
        return ""
