"""
Chat request/response schemas.
"""

import re
from typing import Literal

from pydantic import BaseModel, Field

# Session ID validation pattern
SESSION_ID_PATTERN = re.compile(r"^chat_[a-f0-9]{16}$")


def validate_session_id(value: str) -> str:
    """Validate session ID format."""
    if not SESSION_ID_PATTERN.match(value):
        raise ValueError("Invalid session ID format. Must be: chat_[a-f0-9]{16}")
    return value


class ChatMessage(BaseModel):
    """Chat message schema."""

    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """Chat request schema."""

    messages: list[ChatMessage]
    session_id: str = Field(..., pattern=SESSION_ID_PATTERN.pattern)
    temperature: float = Field(default=0.7, ge=0, le=2)
    max_tokens: int = Field(default=500, ge=1, le=4000)


class ChatResponse(BaseModel):
    """Chat response schema."""

    message: str
    session_id: str
    model: str | None = None
    agents_involved: list[str] | None = None


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
