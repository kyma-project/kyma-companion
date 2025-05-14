from enum import StrEnum

from pydantic import BaseModel


class InitialQuestionsResponse(BaseModel):
    """Response model for the Companion API initial questions."""

    # **IMPORTANT**: DO NOT CHANGE THE RESPONSE MODEL.
    # THE MODEL MUST MATCH THE RESPONSE, BECAUSE KYMA DASHBOARD EXPECTS THIS RESPONSE STRUCTURE.
    # IF THE MODEL CHANGES, THE KYMA DASHBOARD WILL BREAK.
    conversation_id: str
    initial_questions: list[str] = []


class ChunkDataAnswerTaskStatusEnum(StrEnum):
    """Category represents enum for the status of a task."""

    # **IMPORTANT**: DO NOT CHANGE THE RESPONSE MODEL.
    # THE MODEL MUST MATCH THE RESPONSE, BECAUSE KYMA DASHBOARD EXPECTS THIS RESPONSE STRUCTURE.
    # IF THE MODEL CHANGES, THE KYMA DASHBOARD WILL BREAK.

    COMPLETED = "completed"
    PENDING = "pending"
    FAILED = "failed"


class ChunkDataAnswerTask(BaseModel):
    """Response model for the Companion API chunk data answer task."""

    # **IMPORTANT**: DO NOT CHANGE THE RESPONSE MODEL.
    # THE MODEL MUST MATCH THE RESPONSE, BECAUSE KYMA DASHBOARD EXPECTS THIS RESPONSE STRUCTURE.
    # IF THE MODEL CHANGES, THE KYMA DASHBOARD WILL BREAK.

    task_id: int
    task_name: str
    status: ChunkDataAnswerTaskStatusEnum
    agent: str


class ChunkDataAnswer(BaseModel):
    """Response model for the Companion API chunk data answer."""

    # **IMPORTANT**: DO NOT CHANGE THE RESPONSE MODEL.
    # THE MODEL MUST MATCH THE RESPONSE, BECAUSE KYMA DASHBOARD EXPECTS THIS RESPONSE STRUCTURE.
    # IF THE MODEL CHANGES, THE KYMA DASHBOARD WILL BREAK.

    content: str
    tasks: list[ChunkDataAnswerTask]
    next: str


class ChunkData(BaseModel):
    """Response model for the Companion API chunk data."""

    # **IMPORTANT**: DO NOT CHANGE THE RESPONSE MODEL.
    # THE MODEL MUST MATCH THE RESPONSE, BECAUSE KYMA DASHBOARD EXPECTS THIS RESPONSE STRUCTURE.
    # IF THE MODEL CHANGES, THE KYMA DASHBOARD WILL BREAK.

    agent: str
    answer: ChunkDataAnswer
    error: str | None


class ConversationResponseChunk(BaseModel):
    """Response model for the Companion API conversation chunk."""

    # **IMPORTANT**: DO NOT CHANGE THE RESPONSE MODEL.
    # THE MODEL MUST MATCH THE RESPONSE, BECAUSE KYMA DASHBOARD EXPECTS THIS RESPONSE STRUCTURE.
    # IF THE MODEL CHANGES, THE KYMA DASHBOARD WILL BREAK.

    # **IMPORTANT**: DO NOT CHANGE THE RESPONSE MODEL.
    # THE MODEL MUST MATCH THE RESPONSE, BECAUSE KYMA DASHBOARD EXPECTS THIS RESPONSE STRUCTURE.
    # IF THE MODEL CHANGES, THE KYMA DASHBOARD WILL BREAK.
    event: str
    data: ChunkData


class ConversationResponse(BaseModel):
    """Response model for the Companion API conversation."""

    # **IMPORTANT**: DO NOT CHANGE THE RESPONSE MODEL.
    # THE MODEL MUST MATCH THE RESPONSE, BECAUSE KYMA DASHBOARD EXPECTS THIS RESPONSE STRUCTURE.
    # IF THE MODEL CHANGES, THE KYMA DASHBOARD WILL BREAK.
    answer: str
    chunks: list[ConversationResponseChunk]
