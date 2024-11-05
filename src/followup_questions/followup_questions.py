import typing
from typing import Protocol

import tiktoken
from langchain_core.messages import BaseMessage
from langchain_core.messages.utils import get_buffer_string
from langchain_core.prompts import PromptTemplate

from agents.common.utils import filter_messages
from followup_questions.constants import (
    DEFAULT_HISTORY_MESSAGES_LIMIT,
    DEFAULT_TOKEN_LIMIT,
)
from followup_questions.prompts import FOLLOW_UP_QUESTIONS_PROMPT
from initial_questions.inital_questions import IEncoding
from initial_questions.output_parser import QuestionOutputParser
from utils.logging import get_logger
from utils.models import IModel

logger = get_logger(__name__)


class IFollowUpQuestionsHandler(Protocol):
    """Protocol for IFollowUpQuestionsHandler."""

    def generate_questions(self, messages: list[BaseMessage]) -> list[str]:
        """Generates initial questions given a context with cluster data."""
        ...


class FollowUpQuestionsHandler:
    """Handler that generates follow-up questions."""

    _chain: typing.Any
    _model: IModel
    _template: str
    _tokenizer: IEncoding
    _token_limit: int = DEFAULT_TOKEN_LIMIT
    _message_limit: int = DEFAULT_HISTORY_MESSAGES_LIMIT

    def __init__(
        self,
        model: IModel,
        template: str | None = None,
        tokenizer: IEncoding | None = None,
    ) -> None:
        self._model = model
        self._template = template or FOLLOW_UP_QUESTIONS_PROMPT
        prompt = PromptTemplate(
            template=self._template,
            input_variables=["history"],
        )
        output_parser = QuestionOutputParser()
        self._chain = prompt | model.llm | output_parser
        self._tokenizer = tokenizer or tiktoken.encoding_for_model(self._model.name)

    def generate_questions(self, messages: list[BaseMessage]) -> list[str]:
        """Generates follow-up questions given the conversation history."""
        if len(messages) == 0:
            return []

        # filter down the conversation history to limit the token count.
        history = self._get_filtered_history(messages)
        # invoke the chain to generate follow-up questions.
        return self._chain.invoke({"history": history})  # type: ignore

    def _get_prompt_template_token_count(self) -> int:
        """Computes the token count of the prompt template."""
        return len(self._tokenizer.encode(text=self._template))

    def _get_filtered_history(self, messages: list[BaseMessage]) -> str:
        """Reduces the amount of tokens of a string by truncating exceeding tokens."""
        # compute token count of the prompt template.
        template_token_count = self._get_prompt_template_token_count()
        if template_token_count > self._token_limit:
            raise ValueError("Token limit is less than minimum required tokens.")

        # compute available tokens for placing conversation history.
        available_tokens = self._token_limit - template_token_count

        # filter down the conversation history and convert it to string.
        history = get_buffer_string(filter_messages(messages, self._message_limit))
        history_tokens = self._tokenizer.encode(text=history)

        # compute token count of messages.
        text_token_count = len(history_tokens)

        # truncate text if it exceeds the token limit.
        if text_token_count > available_tokens:
            # truncate text from the beginning of string to keep the latest messages.
            return self._tokenizer.decode(tokens=history_tokens[available_tokens + 1 :])
        return history
