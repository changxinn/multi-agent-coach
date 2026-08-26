"""
Chat request/response schemas.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal
import re


# Session ID validation pattern
SESSION_ID_PATTERN = re.compile(r"^chat_[a-f0-9]{16}$")


def validate_session_id(value: str) -> str:
    """Validate session ID format."""
    if not SESSION_ID_PATTERN.match(value):
        raise ValueError(
            "Invalid session ID format. Must be: chat_[a-f0-9]{16}"
        )
    return value


class ChatMessage(BaseModel):
    """Chat message schema."""

    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """Chat request schema."""

    messages: List[ChatMessage]
    session_id: str = Field(..., pattern=SESSION_ID_PATTERN.pattern)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=500, ge=1, le=4000)


class ChatResponse(BaseModel):
    """Chat response schema."""

    message: str
    session_id: str
    model: Optional[str] = None
    agents_involved: Optional[List[str]] = None


class StreamChunk(BaseModel):
    """Streaming response chunk schema."""

    token: str
    session_id: str
    is_complete: bool = False


class SummaryRequest(BaseModel):
    """Summary request schema."""

    session_id: str = Field(..., pattern=SESSION_ID_PATTERN.pattern)


class SummaryResponse(BaseModel):
    """Summary response schema."""

    summary: str
    session_id: str


class ChatHistoryClearRequest(BaseModel):
    """Chat history clear request schema."""

    session_id: str = Field(..., pattern=SESSION_ID_PATTERN.pattern)
