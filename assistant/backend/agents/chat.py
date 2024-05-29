import os
from agents.agent_utils import create_assistant_agent
from helpers.models import create_model, LLM_AZURE_GPT35
from langchain_core.runnables.history import RunnableWithMessageHistory
from llm_commons.langchain.proxy import ChatOpenAI
from langchain_community.chat_message_histories import RedisChatMessageHistory


REDIS_URL = os.environ.get("REDIS_URL")

class AISession:
    def __init__(self, session_id: str, namespace: str = "") -> None:
        self.history = RedisChatMessageHistory(
            session_id, url=REDIS_URL
        )
        self.agent: RunnableWithMessageHistory = create_assistant_agent(self.history, namespace)
        self.init_questions_model: ChatOpenAI = create_model(LLM_AZURE_GPT35)
        self.follow_up_questions_model: ChatOpenAI = create_model(LLM_AZURE_GPT35)
        self.namespace = namespace