from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from agents.common.data import Message
from services.messages import MessagesService


@pytest.mark.asyncio(scope="class")
class TestChat:

    @pytest.mark.asyncio
    async def test_init_chat(self, mock_messaging_service):
        result = await mock_messaging_service.init_chat()
        assert result == {"message": "Chat is initialized!"}

    # @pytest.fixture
    # def mock_model_factory(self, mocker):
    #     mock_factory = MagicMock()
    #     mocker.patch("services.messages.ModelFactory", return_value=mock_factory)
    #     mock_factory.create_model.return_value = MagicMock()

    @pytest.fixture
    def mock_model_factory(self):
        mock_model = Mock()
        with patch("services.messages.ModelFactory") as mock:
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
        with patch("services.messages.KymaGraph", return_value=mock_kyma_graph) as mock:
            yield mock

    @pytest.fixture
    def mock_redis_saver(self):
        with patch("services.messages.RedisSaver") as mock:
            yield mock

    @pytest.fixture
    def mock_init_pool(self):
        with patch("services.messages.initialize_async_pool") as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_handle_request(
        self, mock_model_factory, mock_init_pool, mock_redis_saver, mock_kyma_graph
    ):
        messaging_service = MessagesService()

        message = Message(
            query="Test message",
            resource_type="Pod",
            resource_name="my-pod",
            namespace="default",
        )
        result = [chunk async for chunk in messaging_service.handle_request(1, message)]
        assert result == [b"chunk1\n\n", b"chunk2\n\n", b"chunk3\n\n"]
