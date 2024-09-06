from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from agents.common.data import Message
from agents.memory.conversation_history import ConversationMessage, QueryType
from services.conversation import ConversationService

TIME_STAMP = 1.8
QUESTIONS = ["question1?", "question2?", "question3?"]
CONVERSATION_ID = '1'
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
            pass

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
    def mock_initial_questions_agent(self):
        mock_instance = Mock()
        mock_instance.fetch_relevant_data_from_k8s_cluster = Mock(return_value=POD_YAML)
        mock_instance.generate_questions = Mock(return_value=QUESTIONS)
        with patch("services.conversation.InitialQuestionsAgent", return_value=mock_instance):
            yield mock_instance

    @pytest.mark.asyncio
    async def test_new_conversation(
        self,
        mock_time,
        mock_model_factory,
        mock_init_pool,
        mock_redis_saver,
        mock_kyma_graph,
        mock_initial_questions_agent
    ):
        # Arrange:
        expected_conversation_message = ConversationMessage(
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
            k8s_client=test_k8s_client
        )

        # Assert:
        assert result == QUESTIONS
        mock_redis_saver.return_value.add_conversation_message.assert_called_once_with(
            CONVERSATION_ID, expected_conversation_message
        )
        # Because the InitialQuestionsAgent is a singleton, we cannot guarantee in this test,
        # that its methods were called only once. Therefore, we need to check the last call.
        mock_initial_questions_agent.fetch_relevant_data_from_k8s_cluster.assert_called_with(
            test_message, test_k8s_client
        )
        mock_initial_questions_agent.generate_questions.assert_called_with(context=POD_YAML)

    @pytest.mark.asyncio
    async def test_generate_initial_questions(
        self, 
        mock_model_factory, 
        mock_init_pool, 
        mock_redis_saver, 
        mock_kyma_graph,
        mock_initial_questions_agent
    ):
        # Arrange:
        k8s_client = MagicMock()
        message = Message(
            query="Test message",
            resource_kind="Pod",
            resource_api_version="v1",
            resource_name="my-pod",
            namespace="default",
        )

        # Act:
        messaging_service = ConversationService()
        result = await messaging_service.generate_initial_questions(
            CONVERSATION_ID, message, k8s_client 
        )

        # Assert:
        assert result == QUESTIONS
        # Because the InitialQuestionsAgent is a singleton, we cannot guarantee in this test,
        # that its methods were called only once. Therefore, we need to check the last call.
        messaging_service.init_questions_agent.fetch_relevant_data_from_k8s_cluster.assert_called_with(
            message, k8s_client
        )
        messaging_service.init_questions_agent.generate_questions.assert_called_with(context=POD_YAML)

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
