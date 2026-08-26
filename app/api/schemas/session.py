"""
Session request/response schemas.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
import re

# Session ID validation pattern
SESSION_ID_PATTERN = re.compile(r"^chat_[a-f0-9]{16}$")


class SessionCreateRequest(BaseModel):
    """Session creation request schema."""

    session_id: Optional[str] = Field(None, pattern=SESSION_ID_PATTERN.pattern)  # Frontend-generated or auto-generated
    user_profile: Optional[Dict[str, str]] = None


class SessionResponse(BaseModel):
    """Session response schema."""

    session_id: str
    user_id: int
    created: bool  # True if newly created, False if existing
    profile: Dict[str, str]
    message_count: int = 0


class SessionDetailsResponse(BaseModel):
    """Session details response schema."""

    session_id: str
    user_id: int
    profile: Dict[str, str]
    messages: List[Dict]
    created_at: str
    last_activity: str


class SessionClearRequest(BaseModel):
    """Session clear request schema."""

    session_id: str = Field(..., pattern=SESSION_ID_PATTERN.pattern)
