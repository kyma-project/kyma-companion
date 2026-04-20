"""Tests for model adapter interface, tool call normalization, and helpers."""

from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import AIMessage

from services.model_adapter import (
    AnthropicAdapter,
    ChatResponse,
    GeminiAdapter,
    OpenAIAdapter,
    ToolCall,
    UsageInfo,
    _dicts_to_langchain_messages,
    _extract_usage_from_response,
    _normalize_tool_calls,
    create_model_adapter,
)


class TestToolCall:
    """Tests for ToolCall dataclass."""

    def test_create_tool_call(self):
        tc = ToolCall(id="call_1", name="my_tool", arguments={"key": "value"})
        assert tc.id == "call_1"
        assert tc.name == "my_tool"
        assert tc.arguments == {"key": "value"}


class TestUsageInfo:
    """Tests for UsageInfo dataclass."""

    def test_defaults_to_zero(self):
        usage = UsageInfo()
        assert usage.input_tokens == 0
        assert usage.output_tokens == 0
        assert usage.total_tokens == 0

    def test_custom_values(self):
        usage = UsageInfo(input_tokens=100, output_tokens=50, total_tokens=150)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.total_tokens == 150


class TestChatResponse:
    """Tests for ChatResponse dataclass."""

    def test_defaults(self):
        resp = ChatResponse()
        assert resp.content is None
        assert resp.tool_calls == []
        assert resp.usage is None

    def test_with_content_and_tools(self):
        tc = ToolCall(id="1", name="tool", arguments={})
        resp = ChatResponse(content="answer", tool_calls=[tc], usage=UsageInfo())
        assert resp.content == "answer"
        assert len(resp.tool_calls) == 1


class TestDictsToLangchainMessages:
    """Tests for _dicts_to_langchain_messages converter."""

    def test_system_message(self):
        msgs = _dicts_to_langchain_messages([{"role": "system", "content": "You are helpful."}])
        assert len(msgs) == 1
        assert msgs[0].content == "You are helpful."

    def test_user_message(self):
        msgs = _dicts_to_langchain_messages([{"role": "user", "content": "Hello"}])
        assert len(msgs) == 1
        assert msgs[0].content == "Hello"

    def test_assistant_message_plain(self):
        msgs = _dicts_to_langchain_messages([{"role": "assistant", "content": "Hi"}])
        assert len(msgs) == 1
        assert msgs[0].content == "Hi"

    def test_assistant_message_with_tool_calls(self):
        msgs = _dicts_to_langchain_messages(
            [
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"id": "call_1", "name": "my_tool", "arguments": {"key": "val"}},
                    ],
                }
            ]
        )
        assert len(msgs) == 1
        ai_msg = msgs[0]
        assert len(ai_msg.tool_calls) == 1
        assert ai_msg.tool_calls[0]["name"] == "my_tool"
        assert ai_msg.tool_calls[0]["args"] == {"key": "val"}

    def test_tool_message(self):
        msgs = _dicts_to_langchain_messages(
            [
                {"role": "tool", "content": "result", "tool_call_id": "call_1"},
            ]
        )
        assert len(msgs) == 1
        assert msgs[0].content == "result"

    def test_mixed_messages(self):
        msgs = _dicts_to_langchain_messages(
            [
                {"role": "system", "content": "sys"},
                {"role": "user", "content": "usr"},
                {"role": "assistant", "content": "ast"},
                {"role": "tool", "content": "res", "tool_call_id": "c1"},
            ]
        )
        assert len(msgs) == 4

    def test_missing_content_defaults_to_empty(self):
        msgs = _dicts_to_langchain_messages([{"role": "user"}])
        assert msgs[0].content == ""


class TestNormalizeToolCalls:
    """Tests for _normalize_tool_calls function."""

    def test_no_tool_calls(self):
        response = AIMessage(content="hello")
        assert _normalize_tool_calls(response) == []

    def test_single_tool_call(self):
        response = AIMessage(
            content="",
            tool_calls=[{"id": "c1", "name": "tool_a", "args": {"x": 1}}],
        )
        result = _normalize_tool_calls(response)
        assert len(result) == 1
        assert result[0].id == "c1"
        assert result[0].name == "tool_a"
        assert result[0].arguments == {"x": 1}

    def test_multiple_tool_calls(self):
        response = AIMessage(
            content="",
            tool_calls=[
                {"id": "c1", "name": "tool_a", "args": {}},
                {"id": "c2", "name": "tool_b", "args": {"key": "val"}},
            ],
        )
        result = _normalize_tool_calls(response)
        assert len(result) == 2
        assert result[0].name == "tool_a"
        assert result[1].name == "tool_b"

    def test_missing_fields_default_to_empty(self):
        """When tool call fields are missing in the _normalize_tool_calls input, defaults apply."""
        response = AIMessage(
            content="",
            tool_calls=[{"id": "c_default", "name": "unknown_tool", "args": {}}],
        )
        result = _normalize_tool_calls(response)
        assert result[0].id == "c_default"
        assert result[0].name == "unknown_tool"
        assert result[0].arguments == {}


class TestExtractUsageFromResponse:
    """Tests for _extract_usage_from_response function."""

    def test_no_usage_info(self):
        response = AIMessage(content="hello")
        assert _extract_usage_from_response(response) is None

    def test_token_usage_in_metadata(self):
        response = AIMessage(content="hello")
        response.response_metadata = {
            "token_usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            }
        }
        usage = _extract_usage_from_response(response)
        assert usage is not None
        assert usage.input_tokens == 10
        assert usage.output_tokens == 20
        assert usage.total_tokens == 30

    def test_usage_key_in_metadata(self):
        response = AIMessage(content="hello")
        response.response_metadata = {
            "usage": {
                "input_tokens": 15,
                "output_tokens": 25,
                "total_tokens": 40,
            }
        }
        usage = _extract_usage_from_response(response)
        assert usage is not None
        assert usage.input_tokens == 15
        assert usage.output_tokens == 25
        assert usage.total_tokens == 40

    def test_usage_metadata_attribute(self):
        response = AIMessage(content="hello")
        response.response_metadata = {}
        usage_meta = Mock()
        usage_meta.input_tokens = 5
        usage_meta.output_tokens = 10
        usage_meta.total_tokens = 15
        response.usage_metadata = usage_meta
        usage = _extract_usage_from_response(response)
        assert usage is not None
        assert usage.input_tokens == 5
        assert usage.output_tokens == 10
        assert usage.total_tokens == 15


class TestOpenAIAdapter:
    """Tests for OpenAIAdapter generate methods."""

    @pytest.fixture
    def mock_model(self):
        model = Mock()
        model.name = "gpt-4"
        model.llm = AsyncMock()
        return model

    @pytest.mark.asyncio
    async def test_generate_returns_chat_response(self, mock_model):
        ai_response = AIMessage(content="Test response")
        ai_response.response_metadata = {}
        mock_model.llm.ainvoke = AsyncMock(return_value=ai_response)

        adapter = OpenAIAdapter(mock_model)
        result = await adapter.generate([{"role": "user", "content": "hello"}])

        assert isinstance(result, ChatResponse)
        assert result.content == "Test response"
        assert result.tool_calls == []

    @pytest.mark.asyncio
    async def test_generate_with_tools_returns_tool_calls(self, mock_model):
        ai_response = AIMessage(
            content="",
            tool_calls=[{"id": "c1", "name": "my_tool", "args": {"q": "test"}}],
        )
        ai_response.response_metadata = {}
        llm_with_tools = AsyncMock()
        llm_with_tools.ainvoke = AsyncMock(return_value=ai_response)
        mock_model.llm.bind_tools = Mock(return_value=llm_with_tools)

        adapter = OpenAIAdapter(mock_model)
        result = await adapter.generate_with_tools(
            [{"role": "user", "content": "hello"}],
            [{"type": "function", "function": {"name": "my_tool"}}],
        )

        assert isinstance(result, ChatResponse)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "my_tool"


class TestCreateModelAdapter:
    """Tests for create_model_adapter factory function."""

    def test_creates_openai_adapter_for_gpt(self):
        model = Mock()
        model.name = "gpt-4"
        model.llm = Mock()
        adapter = create_model_adapter(model)
        assert isinstance(adapter, OpenAIAdapter)

    def test_creates_anthropic_adapter_for_anthropic(self):
        model = Mock()
        model.name = "anthropic--claude-4.5-sonnet"
        model.llm = Mock()
        adapter = create_model_adapter(model)
        assert isinstance(adapter, AnthropicAdapter)

    def test_creates_gemini_adapter_for_gemini(self):
        model = Mock()
        model.name = "gemini-1.5-pro"
        model.llm = Mock()
        adapter = create_model_adapter(model)
        assert isinstance(adapter, GeminiAdapter)

    def test_raises_for_unsupported_model(self):
        model = Mock()
        model.name = "llama-3"
        with pytest.raises(ValueError, match="Unsupported model"):
            create_model_adapter(model)


class TestAnthropicAdapter:
    """Tests for AnthropicAdapter content extraction and generation."""

    def _make_adapter(self):
        model = Mock()
        model.name = "anthropic--claude-4.5-sonnet"
        model.llm = AsyncMock()
        return AnthropicAdapter(model)

    def test_extract_content_plain_string(self):
        adapter = self._make_adapter()
        response = AIMessage(content="Hello world")
        assert adapter._extract_content(response) == "Hello world"

    def test_extract_content_empty_string(self):
        adapter = self._make_adapter()
        response = AIMessage(content="")
        assert adapter._extract_content(response) is None

    def test_extract_content_list_with_text_block(self):
        adapter = self._make_adapter()
        response = AIMessage(
            content=[
                {"type": "text", "text": "Here is my analysis."},
            ]
        )
        assert adapter._extract_content(response) == "Here is my analysis."

    def test_extract_content_list_with_text_and_tool_use(self):
        adapter = self._make_adapter()
        response = AIMessage(
            content=[
                {"type": "text", "text": "Let me check that."},
                {"type": "tool_use", "name": "k8s_query_tool", "input": {"uri": "/api/v1/pods"}},
            ]
        )
        assert adapter._extract_content(response) == "Let me check that."

    def test_extract_content_list_with_only_tool_use(self):
        adapter = self._make_adapter()
        response = AIMessage(
            content=[
                {"type": "tool_use", "name": "k8s_query_tool", "input": {"uri": "/api/v1/pods"}},
            ]
        )
        assert adapter._extract_content(response) is None

    def test_extract_content_list_multiple_text_blocks(self):
        adapter = self._make_adapter()
        response = AIMessage(
            content=[
                {"type": "text", "text": "First part."},
                {"type": "text", "text": "Second part."},
            ]
        )
        assert adapter._extract_content(response) == "First part.\nSecond part."

    @pytest.mark.asyncio
    async def test_generate_with_string_content(self):
        adapter = self._make_adapter()
        mock_response = AIMessage(content="Hello!", tool_calls=[])
        adapter._llm.ainvoke = AsyncMock(return_value=mock_response)

        result = await adapter.generate([{"role": "user", "content": "Hi"}])

        assert result.content == "Hello!"
        assert result.tool_calls == []

    @pytest.mark.asyncio
    async def test_generate_with_list_content(self):
        adapter = self._make_adapter()
        mock_response = AIMessage(
            content=[{"type": "text", "text": "Checking..."}, {"type": "tool_use", "name": "test", "input": {}}],
            tool_calls=[{"id": "call_1", "name": "test", "args": {}}],
        )
        adapter._llm.ainvoke = AsyncMock(return_value=mock_response)

        result = await adapter.generate([{"role": "user", "content": "Check something"}])

        assert result.content == "Checking..."
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "test"

    @pytest.mark.asyncio
    async def test_generate_with_tools(self):
        adapter = self._make_adapter()
        mock_response = AIMessage(
            content=[{"type": "tool_use", "name": "k8s_query_tool", "input": {"uri": "/api/v1/pods"}}],
            tool_calls=[{"id": "call_1", "name": "k8s_query_tool", "args": {"uri": "/api/v1/pods"}}],
        )
        mock_bound = AsyncMock()
        mock_bound.ainvoke = AsyncMock(return_value=mock_response)
        adapter._llm.bind_tools = Mock(return_value=mock_bound)

        tools = [{"type": "function", "function": {"name": "k8s_query_tool", "parameters": {}}}]
        result = await adapter.generate_with_tools([{"role": "user", "content": "List pods"}], tools)

        assert result.tool_calls[0].name == "k8s_query_tool"
        adapter._llm.bind_tools.assert_called_once_with(tools)
