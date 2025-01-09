from collections.abc import Callable

from langchain_core.messages import SystemMessage
from langgraph.graph.message import Messages, add_messages

from agents.reducer.sumarization_model_factory import SummarizationModelFactory
from agents.reducer.utils import (
    compute_messages_token_count,
    filter_messages_by_token_limit,
    summarize_messages,
)
from utils import settings
from utils.logging import get_logger
from utils.models.factory import ModelType

logger = get_logger(__name__)


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
    The callback function will retry summarization 3 times before returning a system message with error information.
    """

    # validate the token limits.
    if token_lower_limit >= token_upper_limit:
        raise ValueError(
            f"Token lower limit {token_lower_limit} must be less than token upper limit {token_upper_limit}"
        )

    # initialize the summarization model before returning the callback. So that if the model fails to initialize,
    # then the error is raised early, and the Kyma Graph fails on initialization.
    SummarizationModelFactory().get_chain(summarization_model_type)

    # define the callback reducer function.
    def callback(left: Messages, right: Messages) -> Messages:
        """Callback function that appends new messages and summarizes old messages if the token limit is exceeded."""

        # combine the messages using add_messages. add_messages will also assign the message idsto messages if missing.
        messages = add_messages(left, right)
        if not isinstance(messages, list):
            return messages

        # check if the token count of the combined messages is within the limit.
        token_count = compute_messages_token_count(messages, tokenizer_model_type)
        if token_count <= token_upper_limit:
            return messages

        # filter out messages that can be kept within the token limit.
        latest_messages = filter_messages_by_token_limit(
            list(messages), token_lower_limit, tokenizer_model_type
        )

        if len(latest_messages) == len(messages):
            return messages

        # summarize the remaining old messages, and append the latest messages.
        return add_messages(
            summarize_messages(
                messages[: -len(latest_messages)], summarization_model_type
            ),
            latest_messages,
        )

    # define the callback function with retry logic.
    def callback_with_retry(left: Messages, right: Messages) -> Messages:
        """Callback reducer function with retry logic."""
        err: Exception
        for attempt in range(settings.SUMMARIZATION_RETRY_COUNT):
            try:
                return callback(left, right)
            except Exception as e:
                err = e
                logger.error(
                    f"Summarization attempt {attempt + 1} failed with error: {str(err)}"
                )

        # if the retry count is reached, then add a system message to the messages.
        return add_messages(
            left,
            SystemMessage(
                content=f"Failed to add new messages due to error in summarization: {str(err)}"
            ),
        )

    # return the callback (i.e. reducer) function.
    return callback_with_retry
