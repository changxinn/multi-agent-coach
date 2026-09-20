"""
Session request/response schemas.
"""

import re

from pydantic import BaseModel, Field

# Session ID validation pattern
SESSION_ID_PATTERN = re.compile(r"^chat_[a-f0-9]{16}$")


class SessionCreateRequest(BaseModel):
    """Session creation request schema."""

    session_id: str | None = Field(
        None, pattern=SESSION_ID_PATTERN.pattern
    )  # Frontend-generated or auto-generated
    user_profile: dict[str, str] | None = None


class SessionResponse(BaseModel):
    """Session response schema."""

    session_id: str
    user_id: int
    created: bool  # True if newly created, False if existing
    profile: dict[str, str]
    message_count: int = 0


class SessionDetailsResponse(BaseModel):
    """Session details response schema."""

    session_id: str
    user_id: int
    profile: dict[str, str]
    messages: list[dict]
    created_at: str
    last_activity: str


class SessionClearRequest(BaseModel):
    """Session clear request schema."""

    session_id: str = Field(..., pattern=SESSION_ID_PATTERN.pattern)
