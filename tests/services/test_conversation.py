from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from agents.common.data import Message
from services.conversation import ConversationService

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
    def mock_redis_history(self):
        mock_history = Mock()
        mock_history.add_message = Mock(return_value=None)
        with patch("services.conversation.RedisChatMessageHistory") as mock:
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
        return mock_kyma_graph

    def test_new_conversation(self, mock_redis_history, mock_kyma_graph) -> None:
        # Given:
        mock_handler = Mock()
        mock_handler.fetch_relevant_data_from_k8s_cluster = Mock(return_value=POD_YAML)
        mock_handler.generate_questions = Mock(return_value=QUESTIONS)

        conversation_service = ConversationService(
            initial_questions_handler=mock_handler,
            kyma_graph=mock_kyma_graph,
            redis_url="test",
        )

        mock_k8s_client = Mock()

        # When:
        result = conversation_service.new_conversation(
            session_id=CONVERSATION_ID, k8s_client=mock_k8s_client, message=TEST_MESSAGE
        )

        # Then:
        assert result == QUESTIONS

    @pytest.mark.asyncio(scope="function")
    async def test_handle_request(self, mock_kyma_graph):
        # Given:
        conversation_service = ConversationService(
            initial_questions_handler=Mock(),
            kyma_graph=mock_kyma_graph,
            redis_url="test",
        )

        # When:
        result = [
            chunk
            async for chunk in conversation_service.handle_request(
                CONVERSATION_ID, TEST_MESSAGE
            )
        ]

        # Then:
        assert result == [b"chunk1", b"chunk2", b"chunk3"]
