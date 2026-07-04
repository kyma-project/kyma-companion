"""
Kyma ReAct Agent REST API Router.

Exposes a single endpoint that runs the KymaReActAgent end-to-end and returns
the final answer as a JSON response — no streaming, no supervisor graph.
"""

from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException

from agents.kyma.react_agent import KymaReActAgent
from routers.common import (
    API_PREFIX,
    KymaAgentRequest,
    KymaAgentResponse,
    init_kyma_react_agent,
)
from utils.exceptions import K8sClientError
from utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix=f"{API_PREFIX}/agent/kyma",
    tags=["kyma-agent"],
)


@router.post("/chat", response_model=KymaAgentResponse)
async def kyma_agent_chat(
    request: Annotated[KymaAgentRequest, Body()],
    agent: Annotated[KymaReActAgent, Depends(init_kyma_react_agent)],
) -> KymaAgentResponse:
    """
    Run the Kyma ReAct agent and return the final answer.

    The agent reasons over the query and calls the following tools as needed:
    - `fetch_kyma_resource_version` — resolves unknown resource API versions
    - `kyma_query_tool` — fetches live Kyma resource state from the cluster
    - `search_kyma_doc` — searches official Kyma documentation via RAG

    Returns the agent's final answer once the ReAct loop completes.
    """
    logger.info(f"Kyma agent chat request: query={request.query!r}")

    try:
        answer = await agent.ainvoke(request.query)
        logger.info("Kyma agent chat completed successfully")
        return KymaAgentResponse(answer=answer)
    except K8sClientError as e:
        logger.error(f"K8s error during Kyma agent chat: {e.message}")
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "error": "Kyma agent failed due to a cluster error",
                "message": e.message,
                "uri": e.uri,
            },
        ) from e
    except Exception as e:
        logger.exception("Unexpected error during Kyma agent chat.")
        raise HTTPException(
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="Kyma agent chat failed.",
        ) from e
