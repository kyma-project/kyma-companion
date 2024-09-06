from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from agents.common.data import Message
from agents.memory.conversation_history import ConversationMessage, QueryType
from services.conversation import ConversationService

TIME_STAMP = 1.8
QUESTIONS = ["question1?", "question2?", "question3?"]
CONVERSATION_ID = "1"


@pytest.mark.asyncio(scope="class")
class TestConversation:

    @pytest.fixture
    def mock_time(self):
        with patch("time.time", return_value=TIME_STAMP):
            yield

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
        async def async_mock_add_conversation_message(*args, **kwargs):
            pass  # This method does not return anything

        with patch("services.conversation.RedisSaver") as mock:
            mock.return_value.add_conversation_message = AsyncMock(
                side_effect=async_mock_add_conversation_message
            )
            yield mock

    @pytest.fixture
    def mock_init_pool(self):
        with patch("services.conversation.initialize_async_pool") as mock:
            yield mock

    @pytest.fixture
    def mock_generate_initial_questions(self):
        async def async_mock(*args, **kwargs):
            return QUESTIONS

        with patch.object(
            ConversationService,
            "generate_initial_questions",
            new=AsyncMock(side_effect=async_mock),
        ) as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_new_conversation(
        self,
        mock_time,
        mock_model_factory,
        mock_init_pool,
        mock_redis_saver,
        mock_kyma_graph,
        mock_generate_initial_questions,
    ):
        # Arrange:
        expected_message = ConversationMessage(
            type=QueryType.INITIAL_QUESTIONS,
            query="",
            response="\n".join(QUESTIONS),
            timestamp=TIME_STAMP,
        )

        test_message = Message(
            query="test query",
            resource_kind="Pod",
            resource_api_version="v1",
            resource_name="my-pod",
            namespace="default",
        )
        test_k8s_client = MagicMock()

        # Act:
        messaging_service = ConversationService()
        result = await messaging_service.new_conversation(
            conversation_id=CONVERSATION_ID,
            message=test_message,
            k8s_client=test_k8s_client,
        )

        # Assert:
        mock_generate_initial_questions.assert_called_once_with(
            CONVERSATION_ID, test_message, test_k8s_client
        )
        mock_redis_saver.return_value.add_conversation_message.assert_called_once_with(
            CONVERSATION_ID, expected_message
        )
        assert result == QUESTIONS

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
