from pydantic import BaseModel


class Message(BaseModel):
    """Message data model."""

    query: str
    resource_type: str | None
    resource_name: str | None
    namespace: str | None
