from datetime import datetime

from pydantic import BaseModel, Field


class DailySummaryResponse(BaseModel):
    summary: str
    generated_at: datetime
    reused: bool = False


class HeadCoachRoutingEventResponse(BaseModel):
    id: int
    user_id: int
    session_id: str | None = None
    next_agent: str
    routing_reason: str | None = None
    needs_clarification: bool
    safety_flags: list[str] = Field(default_factory=list)
    user_message: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class CoachSummaryResponse(BaseModel):
    id: int
    user_id: int
    session_id: str | None = None
    summary_type: str
    summary_text: str
    created_at: datetime

    class Config:
        from_attributes = True
