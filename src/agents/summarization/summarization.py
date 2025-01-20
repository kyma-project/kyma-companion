import copy
from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_core.messages import (
    MessageLikeRepresentation,
    RemoveMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langgraph.graph.message import Messages
from pydantic import BaseModel

from agents.common.utils import compute_messages_token_count, compute_string_token_count
from agents.summarization.prompts import MESSAGES_SUMMARIZATION_PROMPT
from utils.models.factory import IModel, ModelType


class Summarization:
    """Summarization helper class."""

    def __init__(
        self,
        model: IModel | Embeddings,
        tokenizer_model_type: ModelType,
        token_lower_limit: int,
        token_upper_limit: int,
        messages_key: str = "messages",
        messages_summary_key: str = "messages_summary",
    ) -> None:
        self._model = model
        self._tokenizer_model_type = tokenizer_model_type
        self._token_lower_limit = token_lower_limit
        self._token_upper_limit = token_upper_limit
        self._messages_key = messages_key
        self._messages_summary_key = messages_summary_key

        # create a chat prompt template for summarization.
        llm_prompt = ChatPromptTemplate.from_messages(
            [
                MessagesPlaceholder(variable_name="messages"),
                ("system", MESSAGES_SUMMARIZATION_PROMPT),
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

    def get_messages_token_count(self, messages: Messages) -> int:
        """Returns the token count of the messages."""
        return compute_messages_token_count(messages, self._tokenizer_model_type)

    def filter_messages_by_token_limit(
        self, messages: list[MessageLikeRepresentation]
    ) -> list[MessageLikeRepresentation]:
        """Returns the messages that can be kept within the token limit."""
        filtered_messages: list[MessageLikeRepresentation] = []
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

    def get_summary(
        self, messages: list[MessageLikeRepresentation], config: RunnableConfig
    ) -> str:
        """Returns the summary of the messages."""
        if len(messages) == 0:
            return ""

        res = self._chain.invoke(
            {"messages": messages},
            config=config,
        )
        return f"Summary of previous chat:\n {res.content}"

    async def summarization_node(
        self, state: BaseModel, config: RunnableConfig
    ) -> dict[str, Any]:
        """Summarization node to summarize the conversation."""
        state_messages = getattr(state, self._messages_key)
        state_messages_summary = getattr(state, self._messages_summary_key)

        all_messages = state_messages
        if state_messages_summary != "":
            # if there is a summary, prepend it to the messages.
            all_messages = [
                SystemMessage(content=state_messages_summary)
            ] + state_messages

        token_count = self.get_messages_token_count(all_messages)
        if token_count <= self.get_token_upper_limit():
            return {
                self._messages_key: [],
            }

        # filter out messages that can be kept within the token limit.
        latest_messages = self.filter_messages_by_token_limit(all_messages)

        if len(latest_messages) == len(all_messages):
            return {
                self._messages_key: [],
            }

        # summarize the remaining old messages
        msgs_for_summarization = all_messages[: -len(latest_messages)]
        summary = self.get_summary(msgs_for_summarization, config)

        # remove excluded messages from state.
        msgs_to_remove = state_messages[: -len(latest_messages)]
        delete_messages = [RemoveMessage(id=m.id) for m in msgs_to_remove]

        return {
            self._messages_summary_key: summary,
            self._messages_key: delete_messages,
        }
