from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.supervisor.agent import Message
from services.chat import Chat


@pytest.mark.asyncio(scope="class")
class TestChat:
    @pytest.fixture
    def mock_supervisor_agent(self):
        mock_supervisor = MagicMock()
        mock_supervisor.astream.return_value = AsyncMock()
        mock_supervisor.astream.return_value.__aiter__.return_value = ["chunk1", "chunk2"]
        return mock_supervisor

    @pytest.fixture
    def chat_instance(self, mock_supervisor_agent):
        with patch("services.chat.Chat.__init__", return_value=None):
            chat_object = Chat()
            chat_object.supervisor_agent = mock_supervisor_agent
            return chat_object

    @pytest.mark.asyncio
    async def test_init_chat(self, chat_instance):
        result = await chat_instance.init_chat()
        assert result == {"message": "Chat is initialized!"}

    @pytest.mark.asyncio
    async def test_handle_request(self, chat_instance, mock_supervisor_agent):
        message = Message(input="Test message", session_id="123")
        result = [chunk async for chunk in chat_instance.handle_request(message)]
        mock_supervisor_agent.astream.assert_called_once_with(message)
        assert result == [b"chunk1\n\n", b"chunk2\n\n"]
