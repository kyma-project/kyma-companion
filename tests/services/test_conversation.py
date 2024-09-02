from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from agents.common.data import Message
from services.conversation import ConversationService


@pytest.mark.asyncio(scope="class")
class TestConversation:

    @pytest.fixture
    def mock_model_factory(self):
        mock_model = Mock()
        with patch("services.conversation.ModelFactory") as mock:
            mock.return_value.create_model.return_value = mock_model
            yield mock

    @pytest.fixture
    def mock_kyma_graph(self):
        mock_kyma_graph = MagicMock()
        mock_kyma_graph.astream.return_value = AsyncMock()
        mock_kyma_graph.astream.return_value.__aiter__.return_value = [
            "chunk1",
            "chunk2",
            "chunk3",
        ]
        with patch(
            "services.conversation.KymaGraph", return_value=mock_kyma_graph
        ) as mock:
            yield mock

    @pytest.fixture
    def mock_redis_saver(self):
        with patch("services.conversation.RedisSaver") as mock:
            yield mock

    @pytest.fixture
    def mock_init_pool(self):
        with patch("services.conversation.initialize_async_pool") as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_init_chat(
        self, mock_model_factory, mock_init_pool, mock_redis_saver, mock_kyma_graph
    ):
        messaging_service = ConversationService()
        result = messaging_service.init_conversation()
        assert result == {"message": "Chat is initialized!"}

    @pytest.mark.asyncio
    async def test_handle_request(
        self, mock_model_factory, mock_init_pool, mock_redis_saver, mock_kyma_graph
    ):
        messaging_service = ConversationService()

        message = Message(
            query="Test message",
            resource_kind="Pod",
            resource_api_version="v1",
            resource_name="my-pod",
            namespace="default",
        )
        result = [chunk async for chunk in messaging_service.handle_request(1, message)]
        assert result == [b"chunk1", b"chunk2", b"chunk3"]
