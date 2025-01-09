import copy

import tiktoken
from langchain_core.messages import (
    MessageLikeRepresentation,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph.message import Messages

from agents.reducer.sumarization_model_factory import SummarizationModelFactory
from utils.models.factory import ModelType


def compute_string_token_count(text: str, model_type: ModelType) -> int:
    """Returns the token count of the string."""
    return len(tiktoken.encoding_for_model(model_type).encode(text=text))


def compute_messages_token_count(msgs: Messages, model_type: ModelType) -> int:
    """Returns the token count of the messages."""
    tokens_per_msg = (
        compute_string_token_count(str(msg.content), model_type) for msg in msgs
    )
    return sum(tokens_per_msg)


def summarize_messages(messages: Messages, model_type: ModelType) -> Messages:
    """Returns the summarized message of the messages."""
    chain = SummarizationModelFactory().get_chain(model_type)
    res = chain.invoke({"messages": messages})
    print("***********SUMMARY************")
    print(res.content)
    return SystemMessage(content=f"Summary of previous messages: {res.content}")


def filter_messages_by_token_limit(
    messages: list[MessageLikeRepresentation], token_limit: int, model_type: ModelType
) -> list[MessageLikeRepresentation]:
    """Returns the messages that can be kept within the token limit."""
    filtered_messages = []
    # iterate the messages in reverse order and keep message if token limit is not exceeded.
    tokens = 0
    for msg in reversed(messages):
        tokens += compute_string_token_count(str(msg.content), model_type)
        if tokens > token_limit:
            break
        filtered_messages.append(copy.deepcopy(msg))

    # remove the tool messages from head of the list,
    # because a tool message must be preceded by a system message.
    for i, message in enumerate(filtered_messages):
        if not isinstance(message, ToolMessage):
            return filtered_messages[i:]
    return filtered_messages
