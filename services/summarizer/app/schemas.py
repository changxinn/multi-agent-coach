from typing import Any

from pydantic import BaseModel, Field


class SummarizeRequest(BaseModel):
    messages: list[dict[str, Any]] = Field(default_factory=list)
    user_profile: dict[str, Any] = Field(default_factory=dict)
    agent_results: list[dict[str, Any]] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)
    progress_text: str = ""
    session_id: str | None = None
    summary_kind: str = "session"


class SummarizeResponse(BaseModel):
    summary: str
    agent: str = "summarizer"
