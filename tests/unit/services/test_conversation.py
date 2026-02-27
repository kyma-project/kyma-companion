import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from kubernetes.client import ApiException
from langchain_core.messages import AIMessage

from agents.common.constants import ERROR, ERROR_RESPONSE
from agents.common.data import Message
from services.conversation import TOKEN_LIMIT, ConversationService
from services.usage import UsageExceedReport
from utils.settings import MAIN_MODEL_MINI_NAME
from utils.singleton_meta import SingletonMeta

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
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Reset singleton instance to ensure test isolation."""
        SingletonMeta.reset_instance(ConversationService)
        yield
        SingletonMeta.reset_instance(ConversationService)

    @pytest.fixture
    def mock_model_factory(self):
        mock_model = Mock()
        mock_models = {MAIN_MODEL_MINI_NAME: mock_model}
        with patch("services.conversation.get_models") as mock_get_models:
            mock_get_models.return_value = mock_models
            yield mock_get_models

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
        with patch("services.conversation.get_async_redis_saver") as mock:
            mock.from_conn_info.return_value = Mock()
            yield mock

    @pytest.fixture
    def mock_config(self):
        mock_config = Mock()
        mock_config.sanitization_config = Mock()
        return mock_config

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_description, k8s_context, fetch_relevant_data_from_k8s_cluster_mock, should_expect_exception",
        [
            (
                "should return questions when k8s context fetch is successful",
                POD_YAML,
                AsyncMock(return_value=POD_YAML),
                False,
            ),
            (
                "should return general questions when k8s context fetch fails due to permission error",
                "No relevant context found",
                AsyncMock(side_effect=ApiException(status=403, reason="Forbidden")),
                False,
            ),
            (
                "should fail when k8s context fetch fails due to any other error",
                "None",
                AsyncMock(side_effect=ApiException(status=404, reason="Unknown")),
                True,
            ),
        ],
    )
    async def test_new_conversation(
        self,
        mock_model_factory,
        mock_companion_graph,
        mock_redis_saver,
        mock_config,
        test_description,
        k8s_context,
        fetch_relevant_data_from_k8s_cluster_mock,
        should_expect_exception,
    ) -> None:
        # Given:
        mock_handler = Mock()
        mock_handler.fetch_relevant_data_from_k8s_cluster = (
            fetch_relevant_data_from_k8s_cluster_mock
        )
        mock_handler.apply_token_limit = Mock(return_value=k8s_context)
        mock_handler.generate_questions = Mock(return_value=QUESTIONS)

        conversation_service = ConversationService(
            config=mock_config,
            initial_questions_handler=mock_handler,
        )

        mock_k8s_client = Mock()

        # When:
        if should_expect_exception:
            with pytest.raises(ApiException):
                await conversation_service.new_conversation(
                    k8s_client=mock_k8s_client, message=TEST_MESSAGE
                )
            return

        result = await conversation_service.new_conversation(
            k8s_client=mock_k8s_client, message=TEST_MESSAGE
        )

        # Then:
        assert result == QUESTIONS
        mock_handler.fetch_relevant_data_from_k8s_cluster.assert_called_once_with(
            message=TEST_MESSAGE, k8s_client=mock_k8s_client
        )
        mock_handler.apply_token_limit.assert_called_once_with(k8s_context, TOKEN_LIMIT)
        mock_handler.generate_questions.assert_called_once_with(context=k8s_context)

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

    @pytest.mark.asyncio
    async def test_handle_request_exception(
        self,
        mock_model_factory,
        mock_redis_saver,
        mock_companion_graph,
        mock_config,
    ):
        mock_k8s_client = Mock()
        mock_companion_graph.astream.side_effect = Exception("stream failure")

        messaging_service = ConversationService(config=mock_config)
        messaging_service._companion_graph = mock_companion_graph

        result = [
            chunk
            async for chunk in messaging_service.handle_request(
                CONVERSATION_ID, TEST_MESSAGE, mock_k8s_client
            )
        ]

        error_response = json.dumps({ERROR: {ERROR: ERROR_RESPONSE}}).encode()
        assert result == [error_response]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_description, conversation_id, user_identifier, thread_owner, expected_result",
        [
            (
                "owner is None, should update owner and authorize",
                "conversation1",
                "user1",
                None,
                True,
            ),
            (
                "owner is the same as user, should authorize",
                "conversation2",
                "user2",
                "user2",
                True,
            ),
            (
                "owner is different from user, should not authorize",
                "conversation3",
                "user3",
                "user4",
                False,
            ),
        ],
    )
    async def test_authorize_user(
        self,
        test_description,
        mock_model_factory,
        mock_redis_saver,
        mock_companion_graph,
        mock_config,
        conversation_id,
        user_identifier,
        thread_owner,
        expected_result,
    ):
        # Given
        mock_companion_graph = Mock()
        mock_companion_graph.aget_thread_owner = AsyncMock(return_value=thread_owner)
        mock_companion_graph.aupdate_thread_owner = AsyncMock()

        conversation_service = ConversationService(config=mock_config)
        conversation_service._companion_graph = mock_companion_graph

        # When
        result = await conversation_service.authorize_user(
            conversation_id, user_identifier
        )

        # Then
        assert result == expected_result
        if thread_owner is None:
            mock_companion_graph.aupdate_thread_owner.assert_called_once_with(
                conversation_id, user_identifier
            )
        else:
            mock_companion_graph.aupdate_thread_owner.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "cluster_id, usage_limit_exceeded",
        [
            (
                "cluster1",
                UsageExceedReport(
                    cluster_id="cluster1",
                    token_limit=100,
                    total_tokens_used=200,
                    reset_seconds_left=1000,
                ),
            ),
            ("cluster2", None),
            (
                "cluster3",
                UsageExceedReport(
                    cluster_id="cluster1",
                    token_limit=500,
                    total_tokens_used=600,
                    reset_seconds_left=3000,
                ),
            ),
        ],
    )
    async def test_is_usage_limit_exceeded(
        self,
        mock_model_factory,
        mock_redis_saver,
        mock_companion_graph,
        mock_config,
        cluster_id,
        usage_limit_exceeded,
    ):
        # Given
        mock_usage_limiter = Mock()
        mock_usage_limiter.adelete_expired_records = AsyncMock()
        mock_usage_limiter.ais_usage_limit_exceeded = AsyncMock(
            return_value=usage_limit_exceeded
        )

        conversation_service = ConversationService(config=mock_config)
        conversation_service._usage_limiter = mock_usage_limiter

        # When
        result = await conversation_service.is_usage_limit_exceeded(cluster_id)

        # Then
        assert result == usage_limit_exceeded
        mock_usage_limiter.adelete_expired_records.assert_called_once_with(cluster_id)
        mock_usage_limiter.ais_usage_limit_exceeded.assert_called_once_with(cluster_id)
