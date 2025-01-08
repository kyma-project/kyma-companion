from collections.abc import Callable

from langgraph.graph.message import Messages, add_messages

from agents.reducer.sumarization_model_factory import SummarizationModelFactory
from agents.reducer.utils import (
    compute_messages_token_count,
    filter_messages_by_token_limit,
    summarize_messages,
)
from utils import settings
from utils.models.factory import ModelType


def new_default_summarization_reducer() -> Callable[[Messages, Messages], Messages]:
    """Returns a LangGraph reducer that appends new messages
    and summarizes old messages if the token limit is exceeded.
    The token limits and summarization model are taken from the settings."""
    return summarize_and_add_messages_token(
        settings.SUMMARIZATION_TOKEN_LOWER_LIMIT,
        settings.SUMMARIZATION_TOKEN_UPPER_LIMIT,
        settings.SUMMARIZATION_MODEL,
        settings.SUMMARIZATION_TOKENIZER_MODEL,
    )


def summarize_and_add_messages_token(
    token_lower_limit: int,
    token_upper_limit: int,
    summarization_model_type: ModelType,
    tokenizer_model_type: ModelType,
) -> Callable[[Messages, Messages], Messages]:
    """Returns a LangGraph reducer that appends new messages and summarizes old messages if the token limit is exceeded.
    Summarization is only triggered when the upper limit is reached.
    The lower limit is used to filter out messages to avoid summarization on every message,
    creating a buffer between the lower and upper limits where summarization will not be triggered.
    """

    # validate the token limits.
    if token_lower_limit >= token_upper_limit:
        raise ValueError(
            f"Token lower limit {token_lower_limit} must be less than token upper limit {token_upper_limit}"
        )

    # initialize the summarization model before returning the callback. So that if the model fails to initialize,
    # then the error is raised early, and the Kyma Graph fails on startup.
    SummarizationModelFactory().get_chain(summarization_model_type)

    # define the callback function that will be returned.
    def callback(left: Messages, right: Messages) -> Messages:
        # combine the messages using add_messages. add_messages will also assign the message ids
        # to messages if missing.
        combined_messages = add_messages(left, right)

        # TODO: add retry logic.
        token_count = compute_messages_token_count(
            combined_messages, tokenizer_model_type
        )
        # if token count is within the limit, return the combined messages.
        if token_count <= token_upper_limit:
            return combined_messages

        # filter out messages that can be kept within the token limit and summarize the excluded messages.
        latest_messages = filter_messages_by_token_limit(
            combined_messages, token_lower_limit, tokenizer_model_type
        )
        if len(latest_messages) == len(combined_messages):
            return combined_messages
        # separate out messages which needs to be summarized.
        msgs_to_be_summarized = combined_messages[: -len(latest_messages)]
        summarized_message = summarize_messages(
            msgs_to_be_summarized, summarization_model_type
        )
        # append the summarized message to the latest messages.
        return add_messages(summarized_message, latest_messages)

    # return the callback (i.e. reducer) function.
    return callback
