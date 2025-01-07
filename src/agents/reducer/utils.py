import tiktoken
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.graph.message import Messages
from agents.reducer.sumarization_model_factory import SummarizationModelFactory
from utils.models.factory import ModelType


def compute_string_token_count(text: str, model_type: ModelType) -> int:
    """Returns the token count of the string."""
    return len(tiktoken.encoding_for_model(model_type.name).encode(text=text))

def compute_messages_token_count(msgs: Messages, model_type: ModelType) -> int:
    """Returns the token count of the messages."""
    return sum(compute_string_token_count(msg.content, model_type) for msg in msgs)

def summarize_messages(messages: Messages, model_type: ModelType) -> Messages:
    chain = SummarizationModelFactory().get_chain(model_type)
    res = chain.invoke({"messages": messages})
    print("***********SUMMARY************")
    print(res.content)
    return SystemMessage(content=f"Summary of previous messages: {res.content}")

def filter_messages_by_token_limit(messages: Messages, token_limit: int) -> Messages:
    """Returns the messages that can be kept within the token limit."""
    # calculate how many latest messages can be kept within the token limit.
    token_count = 0
    msg_count = 0
    for msg in reversed(messages):
        token_count += compute_string_token_count(msg.content)
        if token_count > token_limit:
            break
        msg_count += 1
    # separate out the messages which needs to be kept in chat history.
    filtered_messages = messages[msg_count:].copy()
    # remove the tool messages from head of the list,
    # because a tool message must be preceded by a system message.
    for i, message in enumerate(filtered_messages):
        if not isinstance(message, ToolMessage):
            return filtered_messages[i:]
    return filtered_messages
