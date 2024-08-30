from pydantic import BaseModel

# constants
SESSION_ID_HEADER = "session-id"


# models
class InitialQuestionsResponse(BaseModel):
    initial_questions: list[str] = []
    conversation_id: str
