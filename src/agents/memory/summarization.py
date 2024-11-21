import tiktoken
from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph.message import Messages, add_messages

from agents.memory.prompts import MESSAGES_SUMMARY_PROMPT
from utils.models.factory import ModelFactory, IModel, ModelType
from typing import cast

TOKEN_LIMIT = 10000

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
    return SystemMessage(content=f"Summary of previous messages: {res.content}")

def summarize_and_add_messages(messages_lower_limit, messages_upper_limit):
    def callback(left: Messages, right: Messages) -> Messages:
        combined_messages = add_messages(left, right)

        if len(combined_messages) > messages_upper_limit:
            latest = combined_messages[-messages_lower_limit:]
            summary = get_summary(combined_messages[:-messages_lower_limit])
            return add_messages(summary, latest)

        return combined_messages

    return callback

# def summarize_token_based_and_add_messages(left: Messages, right: Messages) -> Messages:
#     combined_messages = add_messages(left, right)
#
#     # compute token count
#     tokenizer = tiktoken.encoding_for_model(model_4o._model.name)
#     # len(tokenizer.encode(text=self._template))
#
#     # calculate available tokens for messages and summary.
#
#     if len(combined_messages) > MESSAGE_LIMIT:
#         latest =  combined_messages[-MESSAGE_LIMIT:]
#         summary = get_summary(combined_messages[:-MESSAGE_LIMIT])
#         return add_messages(summary, latest)
#
#     return combined_messages

