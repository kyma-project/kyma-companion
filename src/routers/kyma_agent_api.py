"""
Kyma ReAct Agent REST API Router.

Exposes a single endpoint that runs the KymaReActAgent end-to-end and returns
the final answer as a JSON response — no streaming, no supervisor graph.
"""

import json
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Body, Depends, Header, HTTPException
from fastapi.encoders import jsonable_encoder
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from starlette.responses import JSONResponse

from agents.kyma.react_agent import KymaReActAgent, UINavigationContext
from routers.common import (
    API_PREFIX,
    SESSION_ID_HEADER,
    KymaAgentRequest,
    KymaAgentResponse,
    init_kyma_react_agent,
)
from services.redis import Redis
from utils.exceptions import K8sClientError
from utils.logging import get_logger

logger = get_logger(__name__)

KYMA_AGENT_CONVERSATION_PREFIX = "kyma_agent_conversation:"

router = APIRouter(
    prefix=f"{API_PREFIX}/agent/kyma",
    tags=["kyma-agent"],
)


def _serialize_message(message: BaseMessage) -> dict:
    """
    Serialize a BaseMessage to a JSON-serializable dictionary.

    Handles both HumanMessage and AIMessage instances by extracting their
    content and any additional metadata (e.g., tool_calls, name).
    """
    if isinstance(message, HumanMessage):
        return {"type": "human", "content": message.content}
    elif isinstance(message, AIMessage):
        return {
            "type": "ai",
            "content": message.content,
            "tool_calls": getattr(message, "tool_calls", []),
            "name": getattr(message, "name", None),
        }
    else:
        # Fallback: serialize any message type
        return {"type": type(message).__name__, "content": str(message)}


def _deserialize_messages(messages_data: list[dict]) -> list[BaseMessage]:
    """
    Deserialize a list of message dictionaries back into BaseMessage instances.

    Converts serialized message data (stored in Redis) back into HumanMessage
    and AIMessage instances for use with the agent.
    """
    messages: list[BaseMessage] = []
    for msg_data in messages_data:
        msg_type = msg_data.get("type")
        content = msg_data.get("content", "")

        if msg_type == "human":
            messages.append(HumanMessage(content=content))
        elif msg_type == "ai":
            ai_msg = AIMessage(content=content)
            if msg_data.get("tool_calls"):
                ai_msg.tool_calls = msg_data["tool_calls"]
            if msg_data.get("name"):
                ai_msg.name = msg_data["name"]
            messages.append(ai_msg)
        else:
            # Skip unrecognized message types
            continue

    return messages


async def _load_conversation_history(redis_conn: Redis, session_id: str) -> list[BaseMessage]:
    """
    Load conversation history from Redis for the given session_id.

    Returns an empty list if no history exists for this session.
    """
    if not redis_conn.has_connection():
        return []

    try:
        key = f"{KYMA_AGENT_CONVERSATION_PREFIX}{session_id}"
        raw = await redis_conn.get_connection().get(key)
        if raw is None:
            return []

        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")

        messages_data = json.loads(raw)
        return _deserialize_messages(messages_data)
    except Exception:
        logger.exception("Failed to load conversation history from Redis")
        return []


async def _save_conversation_history(redis_conn: Redis, session_id: str, messages: list[BaseMessage]) -> None:
    """
    Save conversation history to Redis for the given session_id.

    Overwrites the previous history with the updated message list.
    """
    if not redis_conn.has_connection():
        return

    try:
        key = f"{KYMA_AGENT_CONVERSATION_PREFIX}{session_id}"
        messages_data = [_serialize_message(msg) for msg in messages]
        serialized = json.dumps(messages_data)
        await redis_conn.get_connection().set(key, serialized, ex=86400)  # 24 hours TTL
    except Exception:
        logger.exception("Failed to save conversation history to Redis")


@router.post("/chat", response_model=KymaAgentResponse)
async def kyma_agent_chat(
    request: Annotated[KymaAgentRequest, Body()],
    agent: Annotated[KymaReActAgent, Depends(init_kyma_react_agent)],
    session_id: Annotated[str, Header()] = "",
) -> JSONResponse:
    """
    Run the Kyma ReAct agent and return the final answer.

    The agent reasons over the query and calls the following tools as needed:
    - `fetch_kyma_resource_version` — resolves unknown resource API versions
    - `kyma_query_tool` — fetches live Kyma resource state from the cluster
    - `search_kyma_doc` — searches official Kyma documentation via RAG

    Conversation history is maintained across requests using the same session_id.
    If no session_id is provided, a new one is generated.

    Returns the agent's final answer once the ReAct loop completes.
    """
    # Generate a session_id if one is not provided
    if not session_id:
        from utils.utils import create_session_id

        session_id = create_session_id()

    logger.info(f"Kyma agent chat request: query={request.query!r}, session_id={session_id}")

    # Load conversation history from Redis
    redis_conn = Redis()
    chat_history = await _load_conversation_history(redis_conn, session_id)

    try:
        ui_context = UINavigationContext(
            resource_kind=request.resource_kind,
            resource_name=request.resource_name,
            resource_api_version=request.resource_api_version,
            namespace=request.namespace,
        )

        # Call the agent with the conversation history
        answer = await agent.ainvoke(request.query, chat_history=chat_history, ui_context=ui_context)

        # Build the new message list including the current user message and AI response
        human_content = request.query
        if ui_context is not None:
            human_content = f"{ui_context.as_context_message()}\n\n{human_content}"

        new_messages = [*chat_history, HumanMessage(content=human_content), AIMessage(content=answer)]

        # Save the updated conversation history to Redis
        await _save_conversation_history(redis_conn, session_id, new_messages)

        logger.info("Kyma agent chat completed successfully")
        return JSONResponse(
            content=jsonable_encoder(KymaAgentResponse(answer=answer)),
            headers={SESSION_ID_HEADER: session_id},
        )
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
