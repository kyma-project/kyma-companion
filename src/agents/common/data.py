from pydantic import BaseModel


class Message(BaseModel):
    """Message data model."""

    query: str
    resource_kind: str | None
    resource_api_version: str | None
    resource_name: str | None
    namespace: str | None
