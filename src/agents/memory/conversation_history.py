from enum import StrEnum

from pydantic import BaseModel


class QueryType(StrEnum):
    """QueryType represents enum for the type of conversation message."""

    INITIAL_QUESTIONS = "initial_questions"
    USER_QUERY = "user_query"


class ConversationMessage(BaseModel):
    """ConversationMessage represents a conversation message stored in Redis."""

    type: QueryType
    query: str
    response: str
    timestamp: float
