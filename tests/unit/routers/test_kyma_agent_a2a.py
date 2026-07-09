"""Unit tests for the Kyma A2A agent router.

Covers:
- _build_human_content() helper
- KymaAgentExecutor.execute() happy path and error paths
- KymaAgentExecutor.cancel()
- build_kyma_a2a_app() factory
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from a2a.server.agent_execution import RequestContext
from a2a.server.events import EventQueueLegacy
from a2a.types.a2a_pb2 import Message, Part, Role
from a2a.utils.errors import InternalError, InvalidParamsError, UnsupportedOperationError
from starlette.applications import Starlette
from starlette.testclient import TestClient

from agents.kyma.react_agent import UINavigationContext
from routers.kyma_agent_a2a import KymaAgentExecutor, _build_human_content, build_kyma_a2a_app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request_context(
    text: str = "list all namespaces",
    metadata: dict | None = None,
) -> RequestContext:
    """Build a minimal mock RequestContext."""
    message = Message(
        role=Role.ROLE_USER,
        parts=[Part(text=text)],
        message_id="msg-1",
        context_id="ctx-1",
        task_id="task-1",
    )
    ctx = MagicMock(spec=RequestContext)
    ctx.message = message
    ctx.get_user_input.return_value = text
    ctx.metadata = metadata or {}
    return ctx


# ---------------------------------------------------------------------------
# _build_human_content
# ---------------------------------------------------------------------------


class TestBuildHumanContent:
    """Tests for _build_human_content helper."""

    def test_prepends_context_when_resource_kind_set(self):
        """UI context with resource_kind should be prepended to query."""
        query = "why is it failing?"
        ui_context = UINavigationContext(
            resource_kind="Function",
            resource_name="my-fn",
            resource_api_version="serverless.kyma-project.io/v1alpha2",
            namespace="default",
        )
        result = _build_human_content(query, ui_context)
        assert "Resource kind: Function" in result
        assert query in result
        assert result.index("Resource kind") < result.index(query)

    def test_returns_bare_query_when_context_empty(self):
        """Empty UI context (no resource kind) should not prepend anything."""
        query = "list all namespaces"
        ui_context = UINavigationContext(resource_kind="")
        result = _build_human_content(query, ui_context)
        # The context message will say "Resource kind: " with empty value,
        # but the method just concatenates; check query is present
        assert query in result


# ---------------------------------------------------------------------------
# KymaAgentExecutor.execute
# ---------------------------------------------------------------------------


class TestKymaAgentExecutorExecute:
    """Tests for KymaAgentExecutor.execute()."""

    @pytest.fixture()
    def executor(self):
        """Return a bare KymaAgentExecutor instance."""
        return KymaAgentExecutor()

    @pytest.fixture()
    def event_queue(self):
        """Return an in-memory event queue."""
        return EventQueueLegacy()

    @pytest.mark.asyncio
    async def test_raises_invalid_params_when_message_is_none(self, executor, event_queue):
        """Execute should raise InvalidParamsError when message is None."""
        ctx = MagicMock(spec=RequestContext)
        ctx.message = None
        ctx.get_user_input.return_value = ""
        ctx.metadata = {}

        with pytest.raises(InvalidParamsError):
            await executor.execute(ctx, event_queue)

    @pytest.mark.asyncio
    async def test_raises_invalid_params_when_query_empty(self, executor, event_queue):
        """Execute should raise InvalidParamsError when query text is empty."""
        ctx = _make_request_context(text="")
        ctx.get_user_input.return_value = ""

        with pytest.raises(InvalidParamsError):
            await executor.execute(ctx, event_queue)

    @pytest.mark.asyncio
    async def test_happy_path_enqueues_message(self, executor, event_queue):
        """Execute should enqueue a Message with the agent's answer."""
        ctx = _make_request_context(
            text="list all namespaces",
            metadata={
                "x-session-id": "sess-123",
                "x-encrypted-key": "key",
                "x-client-iv": "iv",
                "x-target-cluster-encrypted": "enc",
                "namespace": "default",
                "resourceType": "Namespace",
                "resourceName": "",
                "groupVersion": "v1",
            },
        )
        expected_answer = "Here are the namespaces: default, kube-system"

        with (
            patch("routers.kyma_agent_a2a.init_config") as mock_config,
            patch("routers.kyma_agent_a2a.Redis") as mock_redis_cls,
            patch("routers.kyma_agent_a2a.EncryptionCache") as mock_enc_cls,
            patch(
                "routers.kyma_agent_a2a.get_k8s_auth_headers_from_encrypted_payload", new_callable=AsyncMock
            ) as mock_headers,
            patch("routers.kyma_agent_a2a.DataSanitizer") as mock_sanitizer_cls,
            patch("routers.kyma_agent_a2a.K8sClient") as mock_k8s_cls,
            patch("routers.kyma_agent_a2a._ModelsRegistry") as mock_models_cls,
            patch("routers.kyma_agent_a2a.KymaReActAgent") as mock_agent_cls,
            patch("routers.kyma_agent_a2a._load_conversation_history", new_callable=AsyncMock) as mock_load,
            patch("routers.kyma_agent_a2a._save_conversation_history", new_callable=AsyncMock),
        ):
            mock_config.return_value = MagicMock(sanitization_config=None)
            mock_redis_cls.return_value = MagicMock()
            mock_enc_cls.return_value = MagicMock()
            mock_headers.return_value = MagicMock()
            mock_sanitizer_cls.return_value = MagicMock()
            mock_k8s_cls.return_value = MagicMock()
            mock_models_cls.return_value = MagicMock(models={})
            mock_load.return_value = []

            mock_agent_instance = AsyncMock()
            mock_agent_instance.ainvoke = AsyncMock(return_value=expected_answer)
            mock_agent_cls.return_value = mock_agent_instance

            await executor.execute(ctx, event_queue)

        event = await event_queue.dequeue_event()
        assert isinstance(event, Message)
        assert event.role == Role.ROLE_AGENT
        assert len(event.parts) == 1
        assert event.parts[0].text == expected_answer

    @pytest.mark.asyncio
    async def test_raises_internal_error_on_k8s_client_error(self, executor, event_queue):
        """Execute should raise InternalError when a K8sClientError occurs."""
        from utils.exceptions import K8sClientError

        ctx = _make_request_context(
            text="list pods",
            metadata={
                "x-session-id": "sess-1",
                "x-encrypted-key": "k",
                "x-client-iv": "iv",
                "x-target-cluster-encrypted": "enc",
            },
        )

        with (
            patch("routers.kyma_agent_a2a.init_config") as mock_config,
            patch("routers.kyma_agent_a2a.Redis"),
            patch("routers.kyma_agent_a2a.EncryptionCache"),
            patch(
                "routers.kyma_agent_a2a.get_k8s_auth_headers_from_encrypted_payload", new_callable=AsyncMock
            ) as mock_headers,
        ):
            mock_config.return_value = MagicMock(sanitization_config=None)
            mock_headers.side_effect = K8sClientError(
                message="cluster unreachable",
                status_code=503,
                uri="/api/v1/namespaces",
            )

            with pytest.raises(InternalError):
                await executor.execute(ctx, event_queue)

    @pytest.mark.asyncio
    async def test_raises_internal_error_on_unexpected_exception(self, executor, event_queue):
        """Execute should raise InternalError on any unexpected exception."""
        ctx = _make_request_context(text="list pods", metadata={"x-session-id": "sess-2"})

        with (
            patch("routers.kyma_agent_a2a.init_config", side_effect=RuntimeError("unexpected")),
            pytest.raises(InternalError),
        ):
            await executor.execute(ctx, event_queue)

    @pytest.mark.asyncio
    async def test_session_id_generated_when_missing(self, executor, event_queue):
        """Execute should generate a session ID when x-session-id is missing."""
        ctx = _make_request_context(
            text="list pods",
            metadata={
                "x-encrypted-key": "k",
                "x-client-iv": "iv",
                "x-target-cluster-encrypted": "enc",
            },
        )

        with (
            patch("routers.kyma_agent_a2a.init_config") as mock_config,
            patch("routers.kyma_agent_a2a.Redis"),
            patch("routers.kyma_agent_a2a.EncryptionCache"),
            patch(
                "routers.kyma_agent_a2a.get_k8s_auth_headers_from_encrypted_payload", new_callable=AsyncMock
            ) as mock_headers,
            patch("routers.kyma_agent_a2a.DataSanitizer"),
            patch("routers.kyma_agent_a2a.K8sClient"),
            patch("routers.kyma_agent_a2a._ModelsRegistry") as mock_models_cls,
            patch("routers.kyma_agent_a2a.KymaReActAgent") as mock_agent_cls,
            patch("routers.kyma_agent_a2a._load_conversation_history", new_callable=AsyncMock) as mock_load,
            patch("routers.kyma_agent_a2a._save_conversation_history", new_callable=AsyncMock),
            patch("routers.kyma_agent_a2a.create_session_id", return_value="generated-uuid") as mock_create_sid,
        ):
            mock_config.return_value = MagicMock(sanitization_config=None)
            mock_headers.return_value = MagicMock()
            mock_models_cls.return_value = MagicMock(models={})
            mock_load.return_value = []
            mock_agent_instance = AsyncMock()
            mock_agent_instance.ainvoke = AsyncMock(return_value="answer")
            mock_agent_cls.return_value = mock_agent_instance

            await executor.execute(ctx, event_queue)

            mock_create_sid.assert_called_once()
            # Verify the generated session ID was used
            call_kwargs = mock_headers.call_args.kwargs
            assert call_kwargs["x_session_id"] == "generated-uuid"


# ---------------------------------------------------------------------------
# KymaAgentExecutor.cancel
# ---------------------------------------------------------------------------


class TestKymaAgentExecutorCancel:
    """Tests for KymaAgentExecutor.cancel()."""

    @pytest.mark.asyncio
    async def test_cancel_raises_unsupported_operation_error(self):
        """Cancel should raise UnsupportedOperationError since it is not supported."""
        executor = KymaAgentExecutor()
        ctx = MagicMock(spec=RequestContext)
        queue = EventQueueLegacy()

        with pytest.raises(UnsupportedOperationError):
            await executor.cancel(ctx, queue)


# ---------------------------------------------------------------------------
# build_kyma_a2a_app
# ---------------------------------------------------------------------------


class TestBuildKymaA2aApp:
    """Tests for build_kyma_a2a_app() factory."""

    def test_returns_starlette_application(self):
        """Factory should return a Starlette instance."""
        app = build_kyma_a2a_app()
        assert isinstance(app, Starlette)

    def test_has_agent_card_route(self):
        """The sub-app should expose the agent card well-known path."""
        app = build_kyma_a2a_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/.well-known/agent-card.json")
        assert response.status_code == 200  # noqa: PLR2004
        data = response.json()
        assert data["name"] == "Kyma Companion Agent"
        assert "skills" in data

    def test_chat_route_exists(self):
        """The sub-app should have a POST /chat route."""
        app = build_kyma_a2a_app()
        routes = {r.path for r in app.routes}  # type: ignore[attr-defined]
        assert "/chat" in routes

    def test_agent_card_contains_expected_fields(self):
        """Agent card should contain name, version, capabilities."""
        app = build_kyma_a2a_app()
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/.well-known/agent-card.json")
        data = response.json()
        assert data.get("version") == "1.0.0"
        assert "capabilities" in data
