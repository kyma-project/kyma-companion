"""Unit tests for conversation history summarization."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage

from agents.common.conversation_summarizer import (
    ConversationSummarizer,
    format_conversation,
)


def _make_history(num_pairs: int, content: str = "hello") -> list[BaseMessage]:
    """Build a chat history of ``num_pairs`` human/ai message pairs."""
    history: list[BaseMessage] = []
    for i in range(num_pairs):
        history.append(HumanMessage(content=f"{content} question {i}"))
        history.append(AIMessage(content=f"{content} answer {i}"))
    return history


class TestFormatConversation:
    """Tests for format_conversation."""

    def test_roles_are_labeled(self):
        messages = [
            HumanMessage(content="hi"),
            AIMessage(content="hello"),
            SystemMessage(content="ctx"),
        ]
        result = format_conversation(messages)
        assert "User: hi" in result
        assert "Assistant: hello" in result
        assert "System: ctx" in result


class TestConversationSummarizer:
    """Tests for ConversationSummarizer.summarize."""

    @pytest.mark.asyncio
    async def test_summarize_returns_llm_content(self):
        model = MagicMock()
        # PromptTemplate | llm produces a runnable; we bypass by mocking ainvoke_chain
        response = MagicMock()
        response.content = "a concise summary"

        summarizer = ConversationSummarizer(model=model)
        import agents.common.conversation_summarizer as mod

        mod.ainvoke_chain = AsyncMock(return_value=response)

        result = await summarizer.summarize(_make_history(2), config=None)
        assert result == "a concise summary"
        mod.ainvoke_chain.assert_awaited_once()


class TestPrepareChatHistory:
    """Tests for KymaReActAgent._prepare_chat_history."""

    def _agent_with_mocked_summarizer(self, summary: str = "SUMMARY"):
        """Build a bare agent object with only the fields _prepare_chat_history needs."""
        from agents.kyma.react_agent import KymaReActAgent

        agent = KymaReActAgent.__new__(KymaReActAgent)
        agent._conversation_summarizer = MagicMock()
        agent._conversation_summarizer.summarize = AsyncMock(return_value=summary)
        return agent

    @pytest.mark.asyncio
    async def test_empty_history_returns_empty(self):
        agent = self._agent_with_mocked_summarizer()
        result = await agent._prepare_chat_history([], config=None)
        assert result == []

    @pytest.mark.asyncio
    async def test_below_token_limit_returns_raw_history(self, monkeypatch):
        import agents.kyma.react_agent as mod

        monkeypatch.setattr(mod, "CHAT_HISTORY_TOKEN_LIMIT", 100_000)
        agent = self._agent_with_mocked_summarizer()
        history = _make_history(20)
        result = await agent._prepare_chat_history(history, config=None)
        assert result == history
        agent._conversation_summarizer.summarize.assert_not_called()

    @pytest.mark.asyncio
    async def test_above_token_limit_summarizes_older_and_keeps_recent(self, monkeypatch):
        import agents.kyma.react_agent as mod

        monkeypatch.setattr(mod, "CHAT_HISTORY_TOKEN_LIMIT", 1)
        monkeypatch.setattr(mod, "CHAT_HISTORY_KEEP_MESSAGES", 10)
        agent = self._agent_with_mocked_summarizer(summary="OLD SUMMARY")

        history = _make_history(10)  # 20 messages
        result = await agent._prepare_chat_history(history, config=None)

        # 1 summary message + last 10 verbatim
        expected_len = 1 + 10
        assert len(result) == expected_len
        assert isinstance(result[0], SystemMessage)
        assert "OLD SUMMARY" in str(result[0].content)
        assert result[1:] == history[-10:]
        # older 10 messages were summarized
        agent._conversation_summarizer.summarize.assert_awaited_once()
        summarized_arg = agent._conversation_summarizer.summarize.call_args[0][0]
        assert summarized_arg == history[:-10]

    @pytest.mark.asyncio
    async def test_history_smaller_than_keep_window_returned_raw(self, monkeypatch):
        import agents.kyma.react_agent as mod

        monkeypatch.setattr(mod, "CHAT_HISTORY_TOKEN_LIMIT", 1)
        monkeypatch.setattr(mod, "CHAT_HISTORY_KEEP_MESSAGES", 10)
        agent = self._agent_with_mocked_summarizer()

        history = _make_history(3)  # 6 messages < keep window
        result = await agent._prepare_chat_history(history, config=None)
        assert result == history
        agent._conversation_summarizer.summarize.assert_not_called()

    @pytest.mark.asyncio
    async def test_summarizer_failure_falls_back_to_raw_history(self, monkeypatch):
        import agents.kyma.react_agent as mod

        monkeypatch.setattr(mod, "CHAT_HISTORY_TOKEN_LIMIT", 1)
        monkeypatch.setattr(mod, "CHAT_HISTORY_KEEP_MESSAGES", 10)
        agent = self._agent_with_mocked_summarizer()
        agent._conversation_summarizer.summarize = AsyncMock(side_effect=RuntimeError("llm down"))

        history = _make_history(10)
        result = await agent._prepare_chat_history(history, config=None)
        assert result == history
