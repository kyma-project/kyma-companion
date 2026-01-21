from unittest.mock import AsyncMock, Mock

import pytest
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from agents.summarization.summarization import MessageSummarizer
from agents.supervisor.agent import SUPERVISOR
from utils.models.factory import IModel
from utils.settings import MAIN_MODEL_NAME


class TestSummarization:
    @pytest.mark.parametrize(
        "tokenizer_model_name, token_lower_limit, token_upper_limit, messages_key, messages_summary_key",
        [
            (MAIN_MODEL_NAME, 100, 200, "messages", "messages_summary"),
        ],
    )
    def test_init(
        self,
        tokenizer_model_name,
        token_lower_limit,
        token_upper_limit,
        messages_key,
        messages_summary_key,
    ):
        model = Mock(spec=IModel)
        model.llm = Mock()
        summarization = MessageSummarizer(
            model=model,
            tokenizer_model_name=tokenizer_model_name,
            token_lower_limit=token_lower_limit,
            token_upper_limit=token_upper_limit,
            messages_key=messages_key,
            messages_summary_key=messages_summary_key,
        )

        assert summarization._model == model
        assert summarization._tokenizer_model_name == tokenizer_model_name
        assert summarization._token_lower_limit == token_lower_limit
        assert summarization._token_upper_limit == token_upper_limit
        assert summarization._messages_key == messages_key
        assert summarization._messages_summary_key == messages_summary_key
        assert summarization._chain is not None

    @pytest.mark.parametrize(
        "token_upper_limit",
        [
            200,
            300,
            400,
        ],
    )
    def test_get_token_upper_limit(self, token_upper_limit):
        model = Mock(spec=IModel)
        model.llm = Mock()
        summarization = MessageSummarizer(
            model=model,
            tokenizer_model_name=MAIN_MODEL_NAME,
            token_lower_limit=100,
            token_upper_limit=token_upper_limit,
        )
        assert summarization.get_token_upper_limit() == token_upper_limit

    @pytest.mark.parametrize(
        "token_lower_limit",
        [
            200,
            300,
            400,
        ],
    )
    def test_get_token_lower_limit(self, token_lower_limit):
        model = Mock(spec=IModel)
        model.llm = Mock()
        summarization = MessageSummarizer(
            model=model,
            tokenizer_model_name=MAIN_MODEL_NAME,
            token_lower_limit=token_lower_limit,
            token_upper_limit=100,
        )
        assert summarization.get_token_lower_limit() == token_lower_limit

    @pytest.mark.parametrize(
        "messages, model_type, expected_token_count",
        [
            (
                [HumanMessage(content="Hello"), AIMessage(content="Hi there")],
                MAIN_MODEL_NAME,
                3,  # Example token count
            ),
            (
                [
                    HumanMessage(content="This is a test."),
                    AIMessage(content="Another test."),
                ],
                MAIN_MODEL_NAME,
                8,  # Example token count
            ),
            ([], MAIN_MODEL_NAME, 0),  # No messages
            (
                [HumanMessage(content="A longer text input to test the token count.")],
                MAIN_MODEL_NAME,
                10,  # Example token count
            ),
        ],
    )
    def test_get_messages_token_count(self, messages, model_type, expected_token_count):
        model = Mock()
        model.llm = Mock()
        summarization = MessageSummarizer(
            model=model,
            tokenizer_model_name=model_type,
            token_lower_limit=100,
            token_upper_limit=200,
        )
        assert summarization.get_messages_token_count(messages) == expected_token_count

    @pytest.mark.parametrize(
        "messages, token_lower_limit, expected_filtered_messages",
        [
            # Test case, where the token limit is not exceeded.
            (
                [HumanMessage(content="Hello"), AIMessage(content="Hi there")],
                10,
                [HumanMessage(content="Hello"), AIMessage(content="Hi there")],
            ),
            # Test case, where the token limit is exceeded.
            (
                [
                    HumanMessage(content="This is a test."),
                    AIMessage(content="Another test."),
                ],
                5,
                [AIMessage(content="Another test.")],
            ),
            # Test case, where there are no messages.
            (
                [],
                10,
                [],
            ),
            # Test case, where the token limit is not exceeded.
            (
                [HumanMessage(content="A longer text input to test the token count.")],
                10,
                [HumanMessage(content="A longer text input to test the token count.")],
            ),
            # Test case, where a ToolMessage is at the head of list. ToolMessage should be removed from head.
            (
                [
                    ToolMessage(content="Tool message", tool_call_id="call_MEOW"),
                    HumanMessage(content="Human message"),
                ],
                5,
                [HumanMessage(content="Human message")],
            ),
        ],
    )
    def test_filter_messages_by_token_limit(self, messages, token_lower_limit, expected_filtered_messages):
        model = Mock()
        model.llm = Mock()
        summarization = MessageSummarizer(
            model=model,
            tokenizer_model_name=MAIN_MODEL_NAME,
            token_lower_limit=token_lower_limit,
            token_upper_limit=100,
        )
        filtered_messages = summarization.filter_messages_by_token_limit(messages)
        assert filtered_messages == expected_filtered_messages

    @pytest.mark.parametrize(
        "messages, config, expected_summary, mock_response",
        [
            # Existing successful case
            (
                [HumanMessage(content="Hello"), AIMessage(content="Hi there")],
                RunnableConfig(tags=["test"]),
                "Summary of previous chat:\n summary content 1",
                AIMessage(content="summary content 1"),
            ),
            # Empty messages case
            (
                [],
                RunnableConfig(tags=[]),
                "",
                None,  # No mock response needed for empty case
            ),
            # Fallback case when summarization fails
            (
                [
                    HumanMessage(content="This is a test."),
                    AIMessage(content="Another test."),
                ],
                RunnableConfig(tags=[]),
                "Summary of previous chat:\n summary content 2",  # Example summary content
                AIMessage(content="summary content 2"),
            ),
            # Another successful case
            (
                [
                    SystemMessage(content="System message"),
                    HumanMessage(content="A longer text input to test the summary."),
                ],
                RunnableConfig(tags=["test"]),
                "Summary of previous chat:\n summary content 3",
                AIMessage(content="summary content 3"),
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_get_summary(self, messages, config, expected_summary, mock_response):
        model = Mock()
        model.llm = Mock()
        summarization = MessageSummarizer(
            model=model,
            tokenizer_model_name=MAIN_MODEL_NAME,
            token_lower_limit=100,
            token_upper_limit=200,
        )
        summarization._chain = Mock()

        if isinstance(mock_response, Exception):
            summarization._chain.ainvoke = AsyncMock(side_effect=mock_response)
        elif mock_response is not None:
            summarization._chain.ainvoke = AsyncMock(return_value=mock_response)

        result = await summarization.get_summary(messages, config)
        assert result == expected_summary

        # Verify chain invocation
        if messages:
            summarization._chain.ainvoke.assert_called()
        else:
            summarization._chain.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "state_messages, state_messages_summary, token_lower_limit, token_upper_limit, expected_result, error",
        [
            # Test case 1: Successful summarization exceeding the token limit.
            (
                [
                    HumanMessage(id="1", content="This is the first message. It is very long."),
                    AIMessage(id="2", content="This is the second message. It is very long."),
                    HumanMessage(id="3", content="This is the third message. It is very long."),
                    AIMessage(id="4", content="This is the fourth message. It is very long."),
                ],
                "Previous summary",
                20,
                35,
                {
                    "error": None,
                    "messages_summary": "Summary of previous chat:\n summary content",
                    "messages": [
                        RemoveMessage(id="1"),
                        RemoveMessage(id="2"),
                        RemoveMessage(id="3"),
                    ],
                    "next": SUPERVISOR,
                },
                None,
            ),
            # Test case 2: Failed summarization with fallback
            (
                [
                    HumanMessage(id="1", content="This is the first message. It is very long."),
                    AIMessage(id="2", content="This is the second message. It is very long."),
                    HumanMessage(id="3", content="This is the third message. It is very long."),
                    AIMessage(id="4", content="This is the fourth message. It is very long."),
                ],
                "Previous summary",
                20,
                35,
                {
                    "error": "Unexpected error while processing the request. Please try again later.",
                },
                Exception("Summarization failed"),
            ),
            # Test case, where there are no messages.
            ([], "", 100, 200, {"error": None, "messages": []}, None),
            # Test case, where the token limit is not exceeded.
            (
                [
                    SystemMessage(id="1", content="System message"),
                    HumanMessage(id="2", content="A longer text input to test the summary."),
                ],
                "",
                100,
                200,
                {"error": None, "messages": []},
                None,
            ),
        ],
    )
    async def test_summarization_node(
        self,
        state_messages,
        state_messages_summary,
        token_lower_limit,
        token_upper_limit,
        expected_result,
        error,
    ):
        model = Mock(spec=IModel)
        model.llm = Mock()
        summarization = MessageSummarizer(
            model=model,
            tokenizer_model_name=MAIN_MODEL_NAME,
            token_lower_limit=token_lower_limit,
            token_upper_limit=token_upper_limit,
        )
        summarization._chain = Mock()

        # Configure chain mock behavior based on error
        if error:
            summarization._chain.ainvoke = AsyncMock(side_effect=error)
        else:
            summarization._chain.ainvoke = AsyncMock(return_value=AIMessage(content="summary content"))

        class TestState(BaseModel):
            messages: list
            messages_summary: str

        state = TestState(messages=state_messages, messages_summary=state_messages_summary)

        result = await summarization.summarization_node(state, {})
        assert result == expected_result
