from typing import List

from pydantic import BaseModel


class Part(BaseModel):
    text: str


class Content(BaseModel):
    parts: List[Part]
    role: str


class SafetyRating(BaseModel):
    category: str
    probability: str
    probability_score: float
    severity: str
    severity_score: float


class Candidate(BaseModel):
    content: Content
    finish_reason: str
    safety_ratings: List[SafetyRating]


class UsageMetadata(BaseModel):
    candidates_token_count: int
    prompt_token_count: int
    total_token_count: int


class GeminiResponse(BaseModel):
    candidates: List[Candidate]
    usage_metadata: UsageMetadata