from unittest.mock import Mock, patch

import pytest
import tiktoken
from langchain_core.messages import AIMessage, BaseMessage

from followup_questions.constants import (
    DEFAULT_HISTORY_MESSAGES_LIMIT,
    DEFAULT_TOKEN_LIMIT,
)
from followup_questions.followup_questions import FollowUpQuestionsHandler
from followup_questions.prompts import FOLLOW_UP_QUESTIONS_PROMPT


@pytest.fixture
def dummy_conversation_history() -> list[BaseMessage]:
    """Returns a list of dummy conversation history."""
    messages = []
    for i in range(10):
        messages.append(AIMessage(content=f"Message {i}"))
    return messages


class TestFollowUpQuestionsHandler:
    def test_init(self):
        """Test __init__ method."""
        # given
        # define model mock.
        given_model_name = "gpt-4o-mini"
        mock_model = Mock()
        mock_model.name.return_value = given_model_name

        # when
        # initialize FollowUpQuestionsHandler instance.
        given_handler = FollowUpQuestionsHandler(model=mock_model, template=None, tokenizer=None)

        # then
        assert given_handler._model == mock_model
        assert given_handler._template == FOLLOW_UP_QUESTIONS_PROMPT
        assert given_handler._chain is not None
        assert given_handler._tokenizer == tiktoken.encoding_for_model(given_model_name)
        assert given_handler._token_limit == DEFAULT_TOKEN_LIMIT
        assert given_handler._message_limit == DEFAULT_HISTORY_MESSAGES_LIMIT

    @patch(
        "followup_questions.followup_questions.FollowUpQuestionsHandler.__init__",
        return_value=None,
    )
    def test_generate_questions(self, mock, dummy_conversation_history):
        """Test generate_questions method."""
        # given
        # initialize FollowUpQuestionsHandler instance.
        given_handler = FollowUpQuestionsHandler(model=None, template=None, tokenizer=None)

        # define mock for _get_filtered_history method.
        filtered_history = dummy_conversation_history[:2]
        given_handler._get_filtered_history = Mock(return_value=filtered_history)

        # define mock for _chain.invoke method.
        given_handler._chain = Mock()
        dummy_questions = ["question1", "question2", "question3"]
        given_handler._chain.invoke = Mock(return_value=dummy_questions)

        # when
        got_questions = given_handler.generate_questions(dummy_conversation_history)

        # then
        assert got_questions == dummy_questions
        given_handler._get_filtered_history.assert_called_once_with(dummy_conversation_history)
        given_handler._chain.invoke.assert_called_once_with({"history": filtered_history})

    @patch(
        "followup_questions.followup_questions.FollowUpQuestionsHandler.__init__",
        return_value=None,
    )
    def test_get_prompt_template_token_count(self, mock):
        """Test _get_prompt_template_token_count method."""
        # given
        given_model_name = "gpt-4o-mini"
        given_tokenizer = tiktoken.encoding_for_model(given_model_name)
        given_handler = FollowUpQuestionsHandler(model=None)
        given_handler._template = FOLLOW_UP_QUESTIONS_PROMPT
        given_handler._tokenizer = given_tokenizer

        # when
        got_count = given_handler._get_prompt_template_token_count()

        # then
        expected_count = len(given_tokenizer.encode(text=given_handler._template))
        assert expected_count == got_count

    @pytest.mark.parametrize(
        "given_token_limit, given_message_limit, given_prompt_template_token_count, expected_history, expected_error",
        [
            # test case when token limit is less than minimum required.
            (
                400,
                3,
                500,
                "",
                ValueError("Token limit is less than minimum required tokens."),
            ),
            # test case when token limit is not exceeded by the conversation history.
            (
                DEFAULT_TOKEN_LIMIT,
                3,
                500,
                "AI: Message 7\nAI: Message 8\nAI: Message 9",
                None,
            ),
            # test case when token limit is exceeded by the conversation history.
            (
                510,
                3,
                500,
                "\nAI: Message 9",
                None,
            ),
        ],
    )
    def test_get_filtered_history(
        self,
        dummy_conversation_history,
        given_token_limit,
        given_message_limit,
        given_prompt_template_token_count,
        expected_history,
        expected_error,
    ):
        # given
        # define model mock.
        given_model_name = "gpt-4o-mini"
        mock_model = Mock()
        mock_model.name.return_value = given_model_name

        # initialize FollowUpQuestionsHandler instance.
        given_handler = FollowUpQuestionsHandler(model=mock_model, template=None, tokenizer=None)
        given_handler._token_limit = given_token_limit
        given_handler._message_limit = given_message_limit
        given_handler._get_prompt_template_token_count = Mock(return_value=given_prompt_template_token_count)

        if expected_error is not None:
            # when
            with pytest.raises(Exception) as exc_info:
                given_handler._get_filtered_history(dummy_conversation_history)
            # then
            assert isinstance(exc_info.value, type(expected_error))
            assert str(exc_info.value) == str(expected_error)
        else:
            # when
            got_history = given_handler._get_filtered_history(dummy_conversation_history)
            # then
            assert got_history == expected_history
