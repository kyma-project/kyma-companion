from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from langchain_core.messages import AIMessage

from agents.common.data import Message
from services.conversation import TOKEN_LIMIT, ConversationService
from utils.models.factory import ModelType

TIME_STAMP = 1.8
QUESTIONS = ["question1?", "question2?", "question3?"]
CONVERSATION_ID = "1"
POD_YAML = """
apiVersion: v1
kind: Pod
metadata:
  name: my-pod
spec:
  containers:
  - name: my-container
    image: nginx:latest
    ports:
    - containerPort: 80
"""
TEST_MESSAGE = Message(
    query="test query",
    resource_kind="Pod",
    resource_api_version="v1",
    resource_name="my-pod",
    namespace="default",
)


class TestConversation:
    @pytest.fixture
    def mock_model_factory(self):
        mock_model = Mock()
        mock_models = {ModelType.GPT4O_MINI: mock_model}
        with patch("services.conversation.ModelFactory") as mock:
            mock.return_value.create_models.return_value = mock_models
            yield mock

    @pytest.fixture
    def mock_companion_graph(self):
        mock_companion_graph = MagicMock()
        mock_companion_graph.astream.return_value = AsyncMock()
        mock_companion_graph.astream.return_value.__aiter__.return_value = [
            "chunk1",
            "chunk2",
            "chunk3",
        ]
        with patch(
            "services.conversation.CompanionGraph", return_value=mock_companion_graph
        ) as mock:
            yield mock

    @pytest.fixture
    def mock_redis_saver(self):
        with patch("services.conversation.AsyncRedisSaver") as mock:
            mock.from_conn_info.return_value = Mock()
            yield mock

    @pytest.fixture
    def mock_config(self):
        mock_config = Mock()
        mock_config.sanitization_config = Mock()
        return mock_config

    def test_new_conversation(
        self,
        mock_model_factory,
        mock_companion_graph,
        mock_redis_saver,
        mock_config,
    ) -> None:
        # Given:
        mock_handler = Mock()
        mock_handler.fetch_relevant_data_from_k8s_cluster = Mock(return_value=POD_YAML)
        mock_handler.apply_token_limit = Mock(return_value=POD_YAML)
        mock_handler.generate_questions = Mock(return_value=QUESTIONS)
        conversation_service = ConversationService(
            config=mock_config,
            initial_questions_handler=mock_handler,
        )

        mock_k8s_client = Mock()

        # When:
        result = conversation_service.new_conversation(
            k8s_client=mock_k8s_client, message=TEST_MESSAGE
        )

        # Then:
        assert result == QUESTIONS
        mock_handler.fetch_relevant_data_from_k8s_cluster.assert_called_once_with(
            message=TEST_MESSAGE, k8s_client=mock_k8s_client
        )
        mock_handler.apply_token_limit.assert_called_once_with(POD_YAML, TOKEN_LIMIT)
        mock_handler.generate_questions.assert_called_once_with(context=POD_YAML)

    @pytest.mark.asyncio
    async def test_handle_followup_questions(
        self,
        mock_model_factory,
        mock_companion_graph,
        mock_redis_saver,
        mock_config,
    ) -> None:
        # Given:
        dummy_conversation_history = [
            AIMessage(content="Message 1"),
            AIMessage(content="Message 2"),
            AIMessage(content="Message 3"),
        ]
        # define mock for FollowUpQuestionsHandler.
        mock_handler = Mock()
        mock_handler.generate_questions = Mock(return_value=QUESTIONS)
        # initialize ConversationService instance.
        conversation_service = ConversationService(
            config=mock_config,
            followup_questions_handler=mock_handler,
        )
        conversation_service._followup_questions_handler = mock_handler
        # define mock for CompanionGraph.
        conversation_service._companion_graph.aget_messages = AsyncMock(
            return_value=dummy_conversation_history
        )

        # When:
        result = await conversation_service.handle_followup_questions(CONVERSATION_ID)

        # Then:
        assert result == QUESTIONS
        mock_handler.generate_questions.assert_called_once_with(
            messages=dummy_conversation_history
        )
        conversation_service._companion_graph.aget_messages.assert_called_once_with(
            CONVERSATION_ID
        )

    @pytest.mark.asyncio
    async def test_handle_request(
        self,
        mock_model_factory,
        mock_redis_saver,
        mock_companion_graph,
        mock_config,
    ):
        # Given:
        mock_k8s_client = Mock()

        # When:
        messaging_service = ConversationService(config=mock_config)

        # Then:
        result = [
            chunk
            async for chunk in messaging_service.handle_request(
                CONVERSATION_ID, TEST_MESSAGE, mock_k8s_client
            )
        ]
        assert result == [b"chunk1", b"chunk2", b"chunk3"]
