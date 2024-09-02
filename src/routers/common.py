from pydantic import BaseModel

# constants
SESSION_ID_HEADER = "session-id"
API_PREFIX = "/api"


# models
class InitConversationBody(BaseModel):
    resource_kind: str
    resource_name: str
    resource_api_version: str = ""
    namespace: str = ""


class InitialQuestionsResponse(BaseModel):
    initial_questions: list[str] = []
    conversation_id: str
