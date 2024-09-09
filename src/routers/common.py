from pydantic import BaseModel

# constants
SESSION_ID_HEADER = "session-id"
API_PREFIX = "/api"


# models
class InitConversationBody(BaseModel):
    """Request body for initializing a conversation endpoint."""

    resource_kind: str
    resource_name: str
    resource_api_version: str = ""
    namespace: str = ""


class InitialQuestionsResponse(BaseModel):
    """Response body for initializing a conversation endpoint"""

    initial_questions: list[str] = []
    conversation_id: str
