import json
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from kubernetes.client import ApiException

from agents.common.data import Message
from services.conversation import TOKEN_LIMIT, ConversationService
from services.usage import UsageExceedReport
from utils.settings import MAIN_MODEL_MINI_NAME, MAIN_MODEL_NAME

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
        """Reset singleton instances for test isolation."""
        ConversationService._instances = {}
        yield
        ConversationService._instances = {}

    @pytest.fixture
    def mock_model_factory(self):
        mock_model = Mock()
        mock_model.name = "gpt-4.1"
        mock_model.llm = Mock()
        mock_models = {
            MAIN_MODEL_MINI_NAME: mock_model,
            MAIN_MODEL_NAME: mock_model,
        }
        with patch("services.conversation.ModelFactory") as mock:
            mock.return_value.create_models.return_value = mock_models
            yield mock

    @pytest.fixture
    def mock_conversation_store(self):
        store = Mock()
        store.load_messages = AsyncMock(return_value=[])
        store.save_messages = AsyncMock()
        store.get_thread_owner = AsyncMock(return_value=None)
        store.set_thread_owner = AsyncMock()
        with patch("services.conversation.ConversationStore", return_value=store):
            yield store

    @pytest.fixture
    def mock_usage_store(self):
        store = Mock()
        store.awrite_llm_usage = AsyncMock()
        store.adelete_expired_llm_usage_records = AsyncMock()
        store.alist_llm_usage_records = AsyncMock(return_value=[])
        with patch("services.conversation.UsageStore", return_value=store):
            yield store

    @pytest.fixture
    def mock_adapter(self):
        with patch("services.conversation.create_model_adapter") as mock:
            mock.return_value = Mock()
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
        mock_conversation_store,
        mock_usage_store,
        mock_adapter,
        mock_config,
        test_description,
        k8s_context,
        fetch_relevant_data_from_k8s_cluster_mock,
        should_expect_exception,
    ) -> None:
        # Given:
        mock_handler = Mock()
        mock_handler.fetch_relevant_data_from_k8s_cluster = fetch_relevant_data_from_k8s_cluster_mock
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
                await conversation_service.new_conversation(k8s_client=mock_k8s_client, message=TEST_MESSAGE)
            return

        result = await conversation_service.new_conversation(k8s_client=mock_k8s_client, message=TEST_MESSAGE)

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
        mock_conversation_store,
        mock_usage_store,
        mock_adapter,
        mock_config,
    ) -> None:
        # Given:
        dummy_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "What is Kyma?"},
        ]
        mock_conversation_store.load_messages = AsyncMock(return_value=dummy_history)

        mock_handler = Mock()
        mock_handler.generate_questions = Mock(return_value=QUESTIONS)

        conversation_service = ConversationService(
            config=mock_config,
            followup_questions_handler=mock_handler,
        )

        # When:
        result = await conversation_service.handle_followup_questions(CONVERSATION_ID)

        # Then:
        assert result == QUESTIONS
        mock_handler.generate_questions.assert_called_once()
        # Verify LangChain messages were constructed from history
        call_args = mock_handler.generate_questions.call_args
        messages = call_args[1]["messages"]
        assert len(messages) == 3

    @pytest.mark.asyncio
    async def test_handle_request_streams_events(
        self,
        mock_model_factory,
        mock_conversation_store,
        mock_usage_store,
        mock_adapter,
        mock_config,
    ):
        # Given:
        mock_k8s_client = Mock()
        conversation_service = ConversationService(config=mock_config)

        # Mock the CompanionAgent to yield test events
        mock_events = [b'{"event":"agent_action","data":{}}', b'{"event":"agent_action","data":{}}']
        with patch("services.conversation.CompanionAgent") as mock_agent_cls:
            mock_agent = Mock()

            async def mock_handle(*args, **kwargs):
                for event in mock_events:
                    yield event

            mock_agent.handle_message = mock_handle
            mock_agent_cls.return_value = mock_agent

            # When:
            result = [
                chunk async for chunk in conversation_service.handle_request(CONVERSATION_ID, TEST_MESSAGE, mock_k8s_client)
            ]

        # Then:
        assert len(result) == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "test_description, conversation_id, user_identifier, thread_owner, expected_result",
        [
            ("owner is None, should update owner and authorize", "conversation1", "user1", None, True),
            ("owner is the same as user, should authorize", "conversation2", "user2", "user2", True),
            ("owner is different from user, should not authorize", "conversation3", "user3", "user4", False),
        ],
    )
    async def test_authorize_user(
        self,
        test_description,
        mock_model_factory,
        mock_conversation_store,
        mock_usage_store,
        mock_adapter,
        mock_config,
        conversation_id,
        user_identifier,
        thread_owner,
        expected_result,
    ):
        # Given
        mock_conversation_store.get_thread_owner = AsyncMock(return_value=thread_owner)
        mock_conversation_store.set_thread_owner = AsyncMock()

        conversation_service = ConversationService(config=mock_config)

        # When
        result = await conversation_service.authorize_user(conversation_id, user_identifier)

        # Then
        assert result == expected_result
        if thread_owner is None:
            mock_conversation_store.set_thread_owner.assert_called_once_with(conversation_id, user_identifier)
        else:
            mock_conversation_store.set_thread_owner.assert_not_called()

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
        mock_conversation_store,
        mock_usage_store,
        mock_adapter,
        mock_config,
        cluster_id,
        usage_limit_exceeded,
    ):
        # Given
        mock_usage_limiter = Mock()
        mock_usage_limiter.adelete_expired_records = AsyncMock()
        mock_usage_limiter.ais_usage_limit_exceeded = AsyncMock(return_value=usage_limit_exceeded)

        conversation_service = ConversationService(config=mock_config)
        conversation_service._usage_limiter = mock_usage_limiter

        # When
        result = await conversation_service.is_usage_limit_exceeded(cluster_id)

        # Then
        assert result == usage_limit_exceeded
        mock_usage_limiter.adelete_expired_records.assert_called_once_with(cluster_id)
        mock_usage_limiter.ais_usage_limit_exceeded.assert_called_once_with(cluster_id)
