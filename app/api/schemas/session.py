"""
Session request/response schemas.
"""
import re

from pydantic import BaseModel, Field

# Session ID validation pattern
SESSION_ID_PATTERN = re.compile(r"^chat_[a-f0-9]{32}$")


class SessionProfileResponse(BaseModel):
    """Fitness profile included with session responses."""

    user_id: int
    name: str
    fitness_goal: str
    fitness_level: str
    weight_kg: float | None = None
    height_cm: float | None = None
    age: int | None = None


class SessionResponse(BaseModel):
    """Session response schema."""

    session_id: str
    user_id: int
    created: bool  # True if newly created, False if existing
    profile: SessionProfileResponse
    message_count: int = 0


class SessionDetailsResponse(BaseModel):
    """Session details response schema."""

    session_id: str
    user_id: int
    profile: SessionProfileResponse
    messages: list[dict]
    created_at: str
    last_activity: str


class SessionClearRequest(BaseModel):
    """Session clear request schema."""

    session_id: str = Field(..., pattern=SESSION_ID_PATTERN.pattern)
