from pydantic import BaseModel


class Message(BaseModel):
    """Message data model."""

    question: str
