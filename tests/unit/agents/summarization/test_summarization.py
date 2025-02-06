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

from agents.summarization.summarization import Summarization
from utils.models.factory import IModel, ModelType


class TestSummarization:
    @pytest.mark.parametrize(
        "tokenizer_model_type, token_lower_limit, token_upper_limit, messages_key, messages_summary_key",
        [
            (ModelType.GPT4O, 100, 200, "messages", "messages_summary"),
        ],
    )
    def test_init(
        self,
        tokenizer_model_type,
        token_lower_limit,
        token_upper_limit,
        messages_key,
        messages_summary_key,
    ):
        model = Mock(spec=IModel)
        model.llm = Mock()
        summarization = Summarization(
            model=model,
            tokenizer_model_type=tokenizer_model_type,
            token_lower_limit=token_lower_limit,
            token_upper_limit=token_upper_limit,
            messages_key=messages_key,
            messages_summary_key=messages_summary_key,
        )

        assert summarization._model == model
        assert summarization._tokenizer_model_type == tokenizer_model_type
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
        summarization = Summarization(
            model=model,
            tokenizer_model_type=ModelType.GPT4O,
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
        summarization = Summarization(
            model=model,
            tokenizer_model_type=ModelType.GPT4O,
            token_lower_limit=token_lower_limit,
            token_upper_limit=100,
        )
        assert summarization.get_token_lower_limit() == token_lower_limit

    @pytest.mark.parametrize(
        "messages, model_type, expected_token_count",
        [
            (
                [HumanMessage(content="Hello"), AIMessage(content="Hi there")],
                ModelType.GPT4O,
                3,  # Example token count
            ),
            (
                [
                    HumanMessage(content="This is a test."),
                    AIMessage(content="Another test."),
                ],
                ModelType.GPT4O,
                8,  # Example token count
            ),
            ([], ModelType.GPT4O, 0),  # No messages
            (
                [HumanMessage(content="A longer text input to test the token count.")],
                ModelType.GPT4O,
                10,  # Example token count
            ),
        ],
    )
    def test_get_messages_token_count(self, messages, model_type, expected_token_count):
        model = Mock()
        model.llm = Mock()
        summarization = Summarization(
            model=model,
            tokenizer_model_type=model_type,
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
    def test_filter_messages_by_token_limit(
        self, messages, token_lower_limit, expected_filtered_messages
    ):
        model = Mock()
        model.llm = Mock()
        summarization = Summarization(
            model=model,
            tokenizer_model_type=ModelType.GPT4O,
            token_lower_limit=token_lower_limit,
            token_upper_limit=100,
        )
        filtered_messages = summarization.filter_messages_by_token_limit(messages)
        assert filtered_messages == expected_filtered_messages

    @pytest.mark.parametrize(
        "messages, config, expected_summary",
        [
            (
                [HumanMessage(content="Hello"), AIMessage(content="Hi there")],
                RunnableConfig(tags=["test"]),
                "Summary of previous chat:\n summary content",  # Example summary content
            ),
            (
                [
                    HumanMessage(content="This is a test."),
                    AIMessage(content="Another test."),
                ],
                RunnableConfig(tags=[]),
                "Summary of previous chat:\n summary content",  # Example summary content
            ),
            ([], RunnableConfig(tags=["test"]), ""),
            (
                [
                    SystemMessage(content="System message"),
                    HumanMessage(content="A longer text input to test the summary."),
                ],
                RunnableConfig(tags=["test"]),
                "Summary of previous chat:\n summary content",  # Example summary content
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_get_summary(self, messages, config, expected_summary):
        model = Mock()
        model.llm = Mock()
        summarization = Summarization(
            model=model,
            tokenizer_model_type=ModelType.GPT4O,
            token_lower_limit=100,
            token_upper_limit=200,
        )
        summarization._chain = Mock()
        summarization._chain.ainvoke = AsyncMock(
            return_value=AIMessage(content="summary content")
        )
        assert await summarization.get_summary(messages, config) == expected_summary

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "state_messages, state_messages_summary, token_lower_limit, token_upper_limit, expected_result",
        [
            # Test case, where the token limit is exceeded.
            (
                [
                    HumanMessage(
                        id="1", content="This is the first message. It is very long."
                    ),
                    AIMessage(
                        id="2", content="This is the second message. It is very long."
                    ),
                    HumanMessage(
                        id="3", content="This is the third message. It is very long."
                    ),
                    AIMessage(
                        id="4", content="This is the fourth message. It is very long."
                    ),
                ],
                "Previous summary",
                20,
                35,
                {
                    "messages_summary": "Summary of previous chat:\n summary content",
                    "messages": [
                        RemoveMessage(id="1"),
                        RemoveMessage(id="2"),
                        RemoveMessage(id="3"),
                    ],
                },
            ),
            # Test case, where there are no messages.
            ([], "", 100, 200, {"messages": []}),
            # Test case, where the token limit is not exceeded.
            (
                [
                    SystemMessage(id="1", content="System message"),
                    HumanMessage(
                        id="2", content="A longer text input to test the summary."
                    ),
                ],
                "",
                100,
                200,
                {"messages": []},
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
    ):
        model = Mock()
        model.llm = Mock()
        summarization = Summarization(
            model=model,
            tokenizer_model_type=ModelType.GPT4O,
            token_lower_limit=token_lower_limit,
            token_upper_limit=token_upper_limit,
        )
        summarization._chain = Mock()
        summarization._chain.ainvoke = AsyncMock(
            return_value=AIMessage(content="summary content")
        )

        class TestState(BaseModel):
            messages: list
            messages_summary: str

        state = TestState(
            messages=state_messages, messages_summary=state_messages_summary
        )

        result = await summarization.summarization_node(state, {})
        assert result == expected_result
