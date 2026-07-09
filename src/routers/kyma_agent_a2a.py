"""A2A (Agent-to-Agent) executor and sub-app for the Kyma ReAct Agent.

Bridges A2A protocol `message/send` JSON-RPC requests to the existing
KymaReActAgent, extracting K8s authentication and resource context from
message metadata.

Exposed routes (relative to the mount point /api/agent/kyma):
  POST /.well-known/agent-card.json  – agent card discovery
  POST /chat                         – A2A JSON-RPC endpoint
"""

from typing import Any

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentInterface, AgentSkill
from a2a.types.a2a_pb2 import Message, Part, Role
from a2a.utils.errors import InternalError, InvalidParamsError, UnsupportedOperationError
from fastapi import HTTPException
from google.protobuf import json_format
from langchain_core.messages import AIMessage, HumanMessage
from starlette.applications import Starlette
from starlette.routing import Route

from agents.kyma.react_agent import KymaReActAgent, UINavigationContext
from routers.common import (
    _ModelsRegistry,
    _SearchToolRegistry,
    get_k8s_auth_headers_from_encrypted_payload,
    init_config,
    load_conversation_history,
    save_conversation_history,
)
from services.data_sanitizer import DataSanitizer
from services.encryption_cache import EncryptionCache
from services.k8s import K8sClient
from services.redis import Redis
from utils.exceptions import K8sClientError
from utils.logging import get_logger
from utils.utils import create_session_id

logger = get_logger(__name__)


def _build_human_content(query: str, ui_context: UINavigationContext) -> str:
    """Prepend the UI navigation context message to the user query if available.

    Args:
        query: The raw user query string.
        ui_context: The UI navigation context from message metadata.

    Returns:
        Combined context string, or the bare query when context is empty.
    """
    context_message = ui_context.as_context_message()
    if context_message.strip():
        return f"{context_message}\n\n{query}"
    return query


class KymaAgentExecutor(AgentExecutor):
    """A2A AgentExecutor that delegates to the Kyma ReAct Agent.

    Reads K8s cluster authentication and resource context from
    request metadata:
      - x-session-id                → ECDH session for encrypted key lookup
      - x-encrypted-key             → AES key ciphertext
      - x-client-iv                 → AES-GCM nonce
      - x-target-cluster-encrypted  → encrypted cluster auth payload
      - namespace                   → resource namespace (optional)
      - resourceType                → resource kind (optional, e.g. "ConfigMap")
      - resourceName                → resource name (optional)
      - groupVersion                → API version (optional, e.g. "v1")
    """

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute a Kyma agent request and push the result into event_queue.

        Args:
            context: The A2A request context with message and metadata.
            event_queue: Queue to publish the agent response Message to.
        """
        message = context.message
        if message is None:
            raise InvalidParamsError(message="Missing message in request")

        query = context.get_user_input()
        if not query:
            raise InvalidParamsError(message="Empty or missing text in message parts")

        # Use the A2A context_id as the session key for conversation history.
        # If absent, generate a new one and echo it back in the response so the
        # caller can continue the same conversation in subsequent requests.
        session_id = message.context_id or create_session_id()

        # metadata lives in params.message.metadata (protobuf Struct), not
        # params.metadata (request-level, always empty for message/send calls)
        metadata: dict[str, Any] = json_format.MessageToDict(message.metadata) if message.HasField("metadata") else {}
        # Merge with request-level metadata as fallback
        metadata = {**context.metadata, **metadata}

        logger.info(f"A2A Kyma agent request: query={query!r}, session_id={session_id}")

        try:
            config = init_config()
            redis_conn = Redis()
            encryption_cache = EncryptionCache(redis=redis_conn)
            k8s_auth_headers = await get_k8s_auth_headers_from_encrypted_payload(
                x_encrypted_key=str(metadata.get("x-encrypted-key", "")),
                x_client_iv=str(metadata.get("x-client-iv", "")),
                x_session_id=str(metadata.get("x-session-id", "")),
                x_target_cluster_encrypted=str(metadata.get("x-target-cluster-encrypted", "")),
                encryption_cache=encryption_cache,
            )
            data_sanitizer = DataSanitizer(config.sanitization_config)
            k8s_client = K8sClient(k8s_auth_headers=k8s_auth_headers, data_sanitizer=data_sanitizer)

            models = _ModelsRegistry(config).models
            agent = KymaReActAgent(models=models, k8s_client=k8s_client, search_tool=_SearchToolRegistry(models).tool)

            chat_history = await load_conversation_history(redis_conn, session_id)
            ui_context = UINavigationContext(
                resource_kind=str(metadata.get("resourceType", "")),
                resource_name=str(metadata.get("resourceName", "")),
                resource_api_version=str(metadata.get("groupVersion", "")),
                namespace=str(metadata.get("namespace", "")),
            )

            answer = await agent.ainvoke(query, chat_history=chat_history, ui_context=ui_context)

            human_content = _build_human_content(query, ui_context)
            new_messages = [*chat_history, HumanMessage(content=human_content), AIMessage(content=answer)]
            await save_conversation_history(redis_conn, session_id, new_messages)

            response_message = Message(
                role=Role.ROLE_AGENT,
                parts=[Part(text=answer)],
                message_id=message.message_id or "",
                context_id=session_id,
                task_id=message.task_id or "",
            )
            await event_queue.enqueue_event(response_message)

        except HTTPException as exc:
            logger.error(f"HTTP error in A2A Kyma executor: {exc.detail}")
            raise InternalError(message=str(exc.detail)) from exc
        except K8sClientError as exc:
            logger.error(f"K8s error in A2A Kyma executor: {exc.message}")
            raise InternalError(message=exc.message) from exc
        except InternalError:
            raise
        except Exception as exc:
            logger.exception("Unexpected error in A2A Kyma executor")
            raise InternalError(message="Unexpected error during agent execution") from exc

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Cancel is not supported for this agent.

        Args:
            context: The A2A request context (unused).
            event_queue: Event queue (unused).

        Raises:
            UnsupportedOperationError: Always raised; cancellation is not supported.
        """
        raise UnsupportedOperationError(message="Cancellation is not supported by the Kyma agent")


def build_kyma_a2a_app(base_url: str = "http://localhost:8000/api/agent/kyma") -> Starlette:
    """Build and return the Starlette sub-application for the Kyma A2A agent.

    The sub-app is designed to be mounted at /api/agent/kyma in FastAPI via
    ``app.mount("/api/agent/kyma", build_kyma_a2a_app())``.

    Mounted routes (relative paths within the sub-app):
      GET  /.well-known/agent-card.json  – A2A agent card discovery
      POST /chat                         – A2A JSON-RPC (message/send) endpoint

    Args:
        base_url: The public base URL for the agent card (e.g. advertised
                  endpoint in the agent-card). Override in production via
                  the KYMA_A2A_BASE_URL env var or configuration.

    Returns:
        A Starlette application with the A2A JSON-RPC and agent-card routes.
    """
    skill = AgentSkill(
        id="kyma_chat",
        name="Kyma Agent Chat",
        description=(
            "Answers questions about Kyma and Kubernetes resources, "
            "diagnoses cluster issues, and fetches live cluster state."
        ),
        input_modes=["text/plain"],
        output_modes=["text/plain"],
        tags=["kyma", "kubernetes", "k8s", "cluster"],
        examples=["List all namespaces", "Why is my Kyma Function not starting?"],
    )

    agent_card = AgentCard(
        name="Kyma Companion Agent",
        description="AI assistant for Kyma and Kubernetes cluster management (Joule).",
        version="1.0.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(streaming=False, push_notifications=False),
        skills=[skill],
        supported_interfaces=[
            AgentInterface(url=f"{base_url}/chat"),
        ],
    )

    request_handler = DefaultRequestHandler(
        agent_executor=KymaAgentExecutor(),
        task_store=InMemoryTaskStore(),
        agent_card=agent_card,
    )

    routes: list[Route] = []
    routes.extend(create_agent_card_routes(agent_card))
    routes.extend(create_jsonrpc_routes(request_handler, "/chat", enable_v0_3_compat=True))

    app = Starlette(routes=routes)
    return app
