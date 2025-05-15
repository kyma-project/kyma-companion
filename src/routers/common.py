from pydantic import BaseModel

# constants
SESSION_ID_HEADER = "session-id"
API_PREFIX = "/api"


# models
class InitConversationBody(BaseModel):
    """Request body for initializing a conversation endpoint."""

    resource_kind: str
    resource_name: str = ""
    resource_api_version: str = ""
    namespace: str = ""


class InitialQuestionsResponse(BaseModel):
    """Response body for initializing a conversation endpoint"""

    initial_questions: list[str] = []
    conversation_id: str


class FollowUpQuestionsResponse(BaseModel):
    """Response body for follow-up questions endpoint"""

    questions: list[str] = []


class ReadinessModel(BaseModel):
    """Response body representing the state of the Liveness Probe"""

    is_redis_initialized: bool
    is_hana_initialized: bool
    are_models_initialized: bool


class HealthModel(BaseModel):
    """Response body representing the state of the Readiness Probe"""

    is_redis_healthy: bool
    is_hana_healthy: bool
    is_usage_tracker_healthy: bool
    llms: dict[str, bool]
