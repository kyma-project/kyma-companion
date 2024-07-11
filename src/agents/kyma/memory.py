import os

from dotenv import load_dotenv
from langchain_community.chat_message_histories import RedisChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langfuse.callback import CallbackHandler

from utils.models import create_llm

load_dotenv()

langfuse_handler = CallbackHandler(
    secret_key="sk-lf-afa57098-61c8-4373-ad9b-a21aa30c1ddd",
    public_key="pk-lf-c4c35d2b-722c-4c34-acb2-c86370c06e8d",
    host="http://35.246.214.154:3000"
)

llm = create_llm("gpt-4o")

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You're an assistant。"),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{question}"),
    ]
)

chain = prompt | llm

chain_with_history = RunnableWithMessageHistory(
    chain,
    lambda session_id: RedisChatMessageHistory(
        session_id, url=os.getenv("REDIS_URL", "redis://35.246.210.202:6379")
    ),
    input_messages_key="question",
    history_messages_key="history",
)

config = {"configurable": {"session_id": "foo"}, "callbacks": [langfuse_handler]}


def chat_history():  # noqa D103
    chain_with_history.invoke({"question": "Hi! I'm bob"}, config=config)

    chain_with_history.invoke({"question": "Whats my name"}, config=config)
