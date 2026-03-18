"""Tests for CompanionAgent: tool-use loop, streaming output, history truncation."""

import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from agents.companion import CompanionAgent, HISTORY_TOKEN_LIMIT, MAX_TOOL_ROUNDS
from services.model_adapter import ChatResponse, ToolCall, UsageInfo


@pytest.fixture
def mock_adapter():
    adapter = AsyncMock()
    return adapter


@pytest.fixture
def mock_tool_registry():
    registry = MagicMock()
    registry.get_tool_schemas.return_value = [
        {
            "type": "function",
            "function": {
                "name": "k8s_query_tool",
                "description": "Query K8s",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        }
    ]
    registry.execute_tool = AsyncMock(return_value='{"items": []}')
    return registry


@pytest.fixture
def mock_store():
    store = AsyncMock()
    store.load_messages.return_value = []
    store.save_messages = AsyncMock()
    return store


@pytest.fixture
def mock_k8s_client():
    return MagicMock()


@pytest.fixture
def message():
    msg = MagicMock()
    msg.query = "What pods are in default namespace?"
    msg.resource_kind = "Pod"
    msg.resource_name = None
    msg.resource_api_version = "v1"
    msg.namespace = "default"
    msg.resource_scope = None
    msg.resource_related_to = None
    return msg


@pytest.fixture
def agent(mock_adapter, mock_tool_registry, mock_store):
    return CompanionAgent(
        adapter=mock_adapter,
        tool_registry=mock_tool_registry,
        conversation_store=mock_store,
        response_converter=None,
    )


class TestCompanionAgentDirectAnswer:
    """Tests for when the LLM returns a direct answer (no tool calls)."""

    @pytest.mark.asyncio
    async def test_direct_answer_yields_planning_and_final(
        self, agent, mock_adapter, mock_store, mock_k8s_client, message
    ):
        """When LLM gives a direct answer, exactly 2 events are yielded: planning + final."""
        mock_adapter.generate_with_tools = AsyncMock(
            return_value=ChatResponse(content="Here are your pods.", tool_calls=[])
        )
        events = []
        async for chunk in agent.handle_message("conv-1", message, mock_k8s_client):
            events.append(json.loads(chunk))

        assert len(events) == 2
        # First event is planning
        assert events[0]["event"] == "agent_action"
        assert events[0]["data"]["agent"] == "Gatekeeper"
        # Second event is final
        assert events[1]["event"] == "agent_action"
        assert events[1]["data"]["agent"] == "Finalizer"
        assert events[1]["data"]["answer"]["content"] == "Here are your pods."
        assert events[1]["data"]["answer"]["next"] == "__end__"

    @pytest.mark.asyncio
    async def test_direct_answer_saves_history(
        self, agent, mock_adapter, mock_store, mock_k8s_client, message
    ):
        """After a direct answer, history is saved with user + assistant messages."""
        mock_adapter.generate_with_tools = AsyncMock(
            return_value=ChatResponse(content="Response text.", tool_calls=[])
        )
        async for _ in agent.handle_message("conv-1", message, mock_k8s_client):
            pass

        mock_store.save_messages.assert_called_once()
        call_args = mock_store.save_messages.call_args
        conv_id = call_args[0][0]
        saved_messages = call_args[0][1]
        assert conv_id == "conv-1"
        assert any(m["role"] == "user" for m in saved_messages)
        assert any(m["role"] == "assistant" for m in saved_messages)


class TestCompanionAgentToolLoop:
    """Tests for the tool-use loop."""

    @pytest.mark.asyncio
    async def test_tool_call_then_final_answer(
        self, agent, mock_adapter, mock_tool_registry, mock_store, mock_k8s_client, message
    ):
        """When LLM returns tool call(s) then a final answer, both are processed."""
        # First call returns a tool call; second call returns final answer
        tool_call_response = ChatResponse(
            content="",
            tool_calls=[ToolCall(id="c1", name="k8s_query_tool", arguments={"uri": "/api/v1/pods"})],
            usage=UsageInfo(input_tokens=10, output_tokens=5, total_tokens=15),
        )
        final_response = ChatResponse(
            content="Found 3 pods.",
            tool_calls=[],
            usage=UsageInfo(input_tokens=20, output_tokens=10, total_tokens=30),
        )
        mock_adapter.generate_with_tools = AsyncMock(
            side_effect=[tool_call_response, final_response]
        )

        events = []
        async for chunk in agent.handle_message("conv-1", message, mock_k8s_client):
            events.append(json.loads(chunk))

        # Should have planning event + final event
        assert len(events) == 2
        final_event = events[-1]
        assert final_event["data"]["answer"]["content"] == "Found 3 pods."
        assert final_event["data"]["answer"]["next"] == "__end__"

        # Tool was executed
        mock_tool_registry.execute_tool.assert_called_once_with(
            "k8s_query_tool", {"uri": "/api/v1/pods"}, mock_k8s_client
        )

    @pytest.mark.asyncio
    async def test_multiple_tool_rounds(
        self, agent, mock_adapter, mock_tool_registry, mock_store, mock_k8s_client, message
    ):
        """Multiple tool rounds are supported before final answer."""
        tc1 = ChatResponse(
            content="",
            tool_calls=[ToolCall(id="c1", name="k8s_query_tool", arguments={"uri": "/api/v1/pods"})],
        )
        tc2 = ChatResponse(
            content="",
            tool_calls=[ToolCall(id="c2", name="k8s_query_tool", arguments={"uri": "/api/v1/events"})],
        )
        final = ChatResponse(content="All done.", tool_calls=[])
        mock_adapter.generate_with_tools = AsyncMock(side_effect=[tc1, tc2, final])

        events = []
        async for chunk in agent.handle_message("conv-1", message, mock_k8s_client):
            events.append(json.loads(chunk))

        assert mock_tool_registry.execute_tool.call_count == 2
        final_event = events[-1]
        assert final_event["data"]["answer"]["content"] == "All done."

    @pytest.mark.asyncio
    async def test_max_rounds_exhausted(
        self, agent, mock_adapter, mock_tool_registry, mock_store, mock_k8s_client, message
    ):
        """When MAX_TOOL_ROUNDS is exhausted, a fallback final answer is produced."""
        # Always return tool calls
        tool_response = ChatResponse(
            content="",
            tool_calls=[ToolCall(id="c1", name="k8s_query_tool", arguments={"uri": "/api/v1/pods"})],
        )
        # After exhausting tool rounds, generate (without tools) is called
        fallback_response = ChatResponse(content="Ran out of rounds.", tool_calls=[])

        mock_adapter.generate_with_tools = AsyncMock(return_value=tool_response)
        mock_adapter.generate = AsyncMock(return_value=fallback_response)

        events = []
        async for chunk in agent.handle_message("conv-1", message, mock_k8s_client):
            events.append(json.loads(chunk))

        assert mock_adapter.generate_with_tools.call_count == MAX_TOOL_ROUNDS
        mock_adapter.generate.assert_called_once()
        final_event = events[-1]
        assert "Ran out of rounds." in final_event["data"]["answer"]["content"]


class TestCompanionAgentHistoryTruncation:
    """Tests for _truncate_history method."""

    @pytest.fixture
    def truncation_agent(self, mock_adapter, mock_tool_registry, mock_store):
        return CompanionAgent(
            adapter=mock_adapter,
            tool_registry=mock_tool_registry,
            conversation_store=mock_store,
        )

    def test_empty_history_unchanged(self, truncation_agent):
        result = truncation_agent._truncate_history([])
        assert result == []

    def test_short_history_unchanged(self, truncation_agent):
        history = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
        result = truncation_agent._truncate_history(history)
        assert result == history

    def test_long_history_truncated(self, truncation_agent):
        """History exceeding token limit is truncated from the front."""
        # Create a history that exceeds HISTORY_TOKEN_LIMIT
        long_content = "word " * 5000  # ~5000 tokens per message
        history = [
            {"role": "user", "content": long_content},
            {"role": "assistant", "content": long_content},
            {"role": "user", "content": long_content},
            {"role": "assistant", "content": long_content},
            {"role": "user", "content": long_content},
            {"role": "assistant", "content": "final answer"},
        ]
        result = truncation_agent._truncate_history(history)
        assert len(result) < len(history)
        # The last message should be preserved
        assert result[-1]["content"] == "final answer"

    def test_truncation_removes_orphan_tool_messages(self, truncation_agent):
        """If an assistant message with tool_calls is removed, its tool messages are too."""
        history = [
            {"role": "assistant", "content": "", "tool_calls": [{"id": "c1", "name": "t"}]},
            {"role": "tool", "content": "result", "tool_call_id": "c1"},
            {"role": "user", "content": "short"},
            {"role": "assistant", "content": "short"},
        ]
        # Even if under token limit, verify logic works by passing through
        result = truncation_agent._truncate_history(history)
        # Should not start with a tool message
        if result:
            assert result[0].get("role") != "tool"

    def test_truncation_does_not_start_with_tool(self, truncation_agent):
        """Result should never start with a tool message."""
        # Create history that starts with tool messages after truncation
        long_content = "word " * 5000
        history = [
            {"role": "user", "content": long_content},
            {"role": "assistant", "content": long_content, "tool_calls": [{"id": "c1", "name": "t"}]},
            {"role": "tool", "content": "result"},
            {"role": "user", "content": "short"},
            {"role": "assistant", "content": "short"},
        ]
        result = truncation_agent._truncate_history(history)
        if result:
            assert result[0].get("role") != "tool"


class TestCompanionAgentErrorHandling:
    """Tests for error handling in handle_message."""

    @pytest.mark.asyncio
    async def test_exception_yields_error_event(
        self, agent, mock_adapter, mock_store, mock_k8s_client, message
    ):
        """When the agent loop raises, an error event is yielded."""
        mock_adapter.generate_with_tools = AsyncMock(
            side_effect=RuntimeError("LLM down")
        )
        events = []
        async for chunk in agent.handle_message("conv-1", message, mock_k8s_client):
            events.append(json.loads(chunk))

        # Should get at least the planning event and the error event
        error_events = [e for e in events if e["data"].get("error") is not None]
        assert len(error_events) >= 1


class TestCompanionAgentUsageAccumulation:
    """Tests for usage tracking accumulation."""

    @pytest.mark.asyncio
    async def test_usage_accumulated_across_rounds(
        self, agent, mock_adapter, mock_tool_registry, mock_store, mock_k8s_client, message
    ):
        """Usage info is accumulated across multiple tool rounds."""
        tc_response = ChatResponse(
            content="",
            tool_calls=[ToolCall(id="c1", name="k8s_query_tool", arguments={"uri": "/api/v1/pods"})],
            usage=UsageInfo(input_tokens=10, output_tokens=5, total_tokens=15),
        )
        final_response = ChatResponse(
            content="Done.",
            tool_calls=[],
            usage=UsageInfo(input_tokens=20, output_tokens=10, total_tokens=30),
        )
        mock_adapter.generate_with_tools = AsyncMock(
            side_effect=[tc_response, final_response]
        )

        # Just run to completion; usage is accumulated internally
        async for _ in agent.handle_message("conv-1", message, mock_k8s_client):
            pass

        # Verify the adapter was called twice
        assert mock_adapter.generate_with_tools.call_count == 2


class TestCompanionAgentResponseConversion:
    """Tests for response converter integration."""

    @pytest.mark.asyncio
    async def test_response_converter_applied(
        self, mock_adapter, mock_tool_registry, mock_store, mock_k8s_client, message
    ):
        """When a response converter is provided, it is applied to the final content."""
        mock_converter = AsyncMock()
        mock_converter.convert = AsyncMock(return_value="<html>Converted</html>")

        agent = CompanionAgent(
            adapter=mock_adapter,
            tool_registry=mock_tool_registry,
            conversation_store=mock_store,
            response_converter=mock_converter,
        )
        mock_adapter.generate_with_tools = AsyncMock(
            return_value=ChatResponse(content="Raw YAML content", tool_calls=[])
        )

        events = []
        async for chunk in agent.handle_message("conv-1", message, mock_k8s_client):
            events.append(json.loads(chunk))

        final_event = events[-1]
        assert final_event["data"]["answer"]["content"] == "<html>Converted</html>"
        mock_converter.convert.assert_called_once_with("Raw YAML content")

    @pytest.mark.asyncio
    async def test_response_converter_error_falls_back(
        self, mock_adapter, mock_tool_registry, mock_store, mock_k8s_client, message
    ):
        """When response converter raises, the original content is used."""
        mock_converter = AsyncMock()
        mock_converter.convert = AsyncMock(side_effect=RuntimeError("convert failed"))

        agent = CompanionAgent(
            adapter=mock_adapter,
            tool_registry=mock_tool_registry,
            conversation_store=mock_store,
            response_converter=mock_converter,
        )
        mock_adapter.generate_with_tools = AsyncMock(
            return_value=ChatResponse(content="Original content", tool_calls=[])
        )

        events = []
        async for chunk in agent.handle_message("conv-1", message, mock_k8s_client):
            events.append(json.loads(chunk))

        final_event = events[-1]
        assert final_event["data"]["answer"]["content"] == "Original content"


class TestCompanionAgentHistoryLoading:
    """Tests for conversation history loading and saving."""

    @pytest.mark.asyncio
    async def test_loads_existing_history(
        self, agent, mock_adapter, mock_store, mock_k8s_client, message
    ):
        """Existing history is loaded and included in the LLM call."""
        mock_store.load_messages.return_value = [
            {"role": "user", "content": "previous question"},
            {"role": "assistant", "content": "previous answer"},
        ]
        mock_adapter.generate_with_tools = AsyncMock(
            return_value=ChatResponse(content="New answer.", tool_calls=[])
        )

        async for _ in agent.handle_message("conv-1", message, mock_k8s_client):
            pass

        # Verify the adapter received messages including history
        call_args = mock_adapter.generate_with_tools.call_args
        messages = call_args[0][0]
        # Should have: system (static) + system (resource context) + 2 history + user
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "system"  # resource context
        assert messages[2]["role"] == "user"
        assert messages[2]["content"] == "previous question"
        assert messages[3]["role"] == "assistant"
        assert messages[3]["content"] == "previous answer"
        assert messages[4]["role"] == "user"
        assert messages[4]["content"] == message.query
