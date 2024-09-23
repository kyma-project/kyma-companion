from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from agents.common.data import Message
from agents.graph import IGraph
from initial_questions.inital_questions import (
    IInitialQuestionsHandler,
)
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


@pytest.mark.asyncio(scope="class")
class TestConversation:
    @pytest.fixture
    def mock_handler(self) -> IInitialQuestionsHandler:
        mock_handler = Mock()
        mock_handler.fetch_relevant_data_from_k8s_cluster = Mock(return_value=POD_YAML)
        mock_handler.generate_questions = Mock(return_value=QUESTIONS)
        return mock_handler

    @pytest.fixture
    def mock_kyma_graph(self) -> IGraph:
        mock_kyma_graph = MagicMock()
        mock_kyma_graph.astream.return_value = AsyncMock()
        mock_kyma_graph.astream.return_value.__aiter__.return_value = [
            "chunk1",
            "chunk2",
            "chunk3",
        ]
        return mock_kyma_graph

    def test_new_conversation(self, mock_handler, mock_kyma_graph) -> None:
        # Given:
        conversation_service = ConversationService(
            redis_url="test",
            initial_questions_handler=mock_handler,
            kyma_graph=mock_kyma_graph,
        )

        mock_k8s_client = Mock()

        # When:
        result = conversation_service.new_conversation(
            session_id=CONVERSATION_ID, k8s_client=mock_k8s_client, message=TEST_MESSAGE
        )

        # Then:
        assert result == QUESTIONS

    @pytest.mark.asyncio
    async def test_handle_request(self, mock_handler, mock_kyma_graph):
        # Given:
        conversation_service = ConversationService(
            redis_url="test",
            initial_questions_handler=mock_handler,
            kyma_graph=mock_kyma_graph,
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
