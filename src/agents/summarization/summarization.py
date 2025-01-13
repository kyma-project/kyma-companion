import copy

from langchain_core.messages import (
    MessageLikeRepresentation,
    ToolMessage,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import Messages

from agents.common.utils import compute_messages_token_count, compute_string_token_count
from agents.summarization.prompts import MESSAGES_SUMMARIZATION_PROMPT
from utils.models.factory import IModel, ModelType


class Summarization:
    """Summarization helper class."""

    def __init__(
        self,
        model: IModel,
        tokenizer_model_type: ModelType,
        token_lower_limit: int,
        token_upper_limit: int,
    ) -> None:
        self._model = model
        self._tokenizer_model_type = tokenizer_model_type
        self._token_lower_limit = token_lower_limit
        self._token_upper_limit = token_upper_limit

        # create a chat prompt template for summarization.
        llm_prompt = ChatPromptTemplate.from_messages(
            [
                MessagesPlaceholder(variable_name="messages"),
            ]
        )
        # get the summarization model.
        self._chain = llm_prompt | self._model.llm

    def get_token_upper_limit(self) -> int:
        """Returns the token upper limit."""
        return self._token_upper_limit

    def get_token_lower_limit(self) -> int:
        """Returns the token lower limit."""
        return self._token_lower_limit

    def get_messages_token_count(self, messages: Messages) -> str:
        """Returns the token count of the messages."""
        return compute_messages_token_count(messages, self._tokenizer_model_type)

    def filter_messages_by_token_limit(
        self, messages: list[MessageLikeRepresentation]
    ) -> list[MessageLikeRepresentation]:
        """Returns the messages that can be kept within the token limit."""
        filtered_messages = []
        # iterate the messages in reverse order and keep message if token limit is not exceeded.
        tokens = 0
        for msg in reversed(messages):
            tokens += compute_string_token_count(
                str(msg.content), self._tokenizer_model_type
            )
            if tokens > self._token_lower_limit:
                break
            filtered_messages.insert(0, copy.deepcopy(msg))

        # remove the tool messages from head of the list,
        # because a tool message must be preceded by a system message.
        for i, message in enumerate(filtered_messages):
            if not isinstance(message, ToolMessage):
                return filtered_messages[i:]
        return filtered_messages

    def get_summary(self, messages: Messages, config: RunnableConfig) -> str:
        """Returns the summary of the messages."""
        if len(messages) == 0:
            return ""

        if "tags" not in config:
            config["tags"] = ["summarization"]
        else:
            config["tags"].append("summarization")

        res = self._chain.invoke(
            {"messages": messages + [("system", MESSAGES_SUMMARIZATION_PROMPT)]},
            config=config,
        )
        return f"Summary of previous chat:\n {res.content}"
