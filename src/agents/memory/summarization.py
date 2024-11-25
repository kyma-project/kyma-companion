import tiktoken
from langchain_core.messages import SystemMessage, ToolMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph.message import Messages, add_messages

from agents.memory.prompts import MESSAGES_SUMMARY_PROMPT
from utils.models.factory import ModelFactory, IModel, ModelType
from typing import cast

MESSAGES_LOWER_LIMIT = 10
MESSAGES_UPPER_LIMIT = 15

TOKEN_LOWER_LIMIT = 1000
TOKEN_UPPER_LIMIT = 2000

model_factory = ModelFactory()
models = model_factory.create_models()
model_4o = cast(IModel, models[ModelType.GPT4O])

def get_summary(messages: Messages) -> Messages:
    llm_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", MESSAGES_SUMMARY_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
        ]
    )

    chain = llm_prompt | model_4o.llm
    res = chain.invoke({"messages": messages})
    print("***********SUMMARY************")
    print(res.content)
    return SystemMessage(content=f"Summary of previous messages: {res.content}")

# def summarize_and_add_messages(messages_lower_limit, messages_upper_limit):
#     def callback(left: Messages, right: Messages) -> Messages:
#         combined_messages = add_messages(left, right)
#
#         if len(combined_messages) > messages_upper_limit:
#             latest = combined_messages[-messages_lower_limit:]
#             summary = get_summary(combined_messages[:-messages_lower_limit])
#             return add_messages(summary, latest)
#
#         return combined_messages
#
#     return callback


def compute_string_token_count(text: str) -> int:
    tokenizer = tiktoken.encoding_for_model(model_4o.name)
    return len(tokenizer.encode(text=text))

def compute_messages_token_count(msgs: Messages) -> int:
    token_count = 0
    for msg in msgs:
        token_count += compute_string_token_count(msg.content)
    return token_count

def filter_messages_by_token_limit(messages: Messages, token_limit: int) -> Messages:
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

def summarize_and_add_messages_token(token_lower_limit, token_upper_limit):
    def callback(left: Messages, right: Messages) -> Messages:
        combined_messages = add_messages(left, right)

        token_count = compute_messages_token_count(combined_messages)
        if token_count > token_upper_limit:
            latest_messages = filter_messages_by_token_limit(combined_messages, token_lower_limit)
            if len(latest_messages) == len(combined_messages):
                return combined_messages
            # separate out messages which needs to be summarized.
            msgs_for_summary = combined_messages[:-len(latest_messages)]
            summary = get_summary(msgs_for_summary)
            return add_messages(summary, latest_messages)
        return combined_messages
    return callback

