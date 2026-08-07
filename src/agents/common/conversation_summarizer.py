"""Summarize older conversation history to keep prompt token usage bounded."""

from typing import Protocol

from langchain_core.embeddings import Embeddings
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables.config import RunnableConfig

from agents.common.prompts import CONVERSATION_SUMMARIZER_PROMPT
from utils.chain import ainvoke_chain
from utils.logging import get_logger
from utils.models.factory import IModel

logger = get_logger(__name__)


def _role_of(message: BaseMessage) -> str:
    """Return a human-readable role label for a message."""
    if isinstance(message, HumanMessage):
        return "User"
    if isinstance(message, AIMessage):
        return "Assistant"
    if isinstance(message, SystemMessage):
        return "System"
    return message.__class__.__name__


def format_conversation(messages: list[BaseMessage]) -> str:
    """Render a list of messages into a readable transcript for summarization."""
    return "\n\n".join(f"{_role_of(msg)}: {str(msg.content)}" for msg in messages)


class IConversationSummarizer(Protocol):
    """Protocol for conversation history summarizers."""

    async def summarize(self, messages: list[BaseMessage], config: RunnableConfig | None = None) -> str:
        """Summarize the given conversation messages into a concise recap."""
        ...


class ConversationSummarizer:
    """Summarize older conversation turns into a concise context paragraph."""

    def __init__(self, model: IModel | Embeddings):
        self.model = model

    async def summarize(self, messages: list[BaseMessage], config: RunnableConfig | None = None) -> str:
        """Summarize the given conversation messages into a concise recap."""
        if not messages:
            return ""
        chain = (
            PromptTemplate(
                template=CONVERSATION_SUMMARIZER_PROMPT,
                input_variables=["conversation"],
            )
            | self.model.llm
        )
        response = await ainvoke_chain(
            chain,
            {"conversation": format_conversation(messages)},
            config=config,
        )
        return str(response.content)
