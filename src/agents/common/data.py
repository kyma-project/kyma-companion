from pydantic import BaseModel


class Message(BaseModel):
    """
    Message data model.
    Because of Pydantic version conflict between AICore and LangGraph, we keep this model as a duplicate of UserInput.
    """

    query: str
    resource_kind: str | None
    resource_api_version: str | None
    resource_name: str | None
    namespace: str | None
