"""Persistence for Head Coach routing events and summarizer output."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CoachSummary, HeadCoachRoutingEvent


def utc_day_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return [start, end) for the UTC calendar day, timezone-aware."""
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    start = current.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


class CoachEventsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_routing_event(
        self,
        *,
        user_id: int,
        session_id: str | None,
        next_agent: str,
        routing_reason: str | None,
        needs_clarification: bool,
        safety_flags: list[str],
        user_message: str | None,
    ) -> HeadCoachRoutingEvent:
        event = HeadCoachRoutingEvent(
            user_id=user_id,
            session_id=session_id,
            next_agent=next_agent,
            routing_reason=routing_reason,
            needs_clarification=needs_clarification,
            safety_flags=safety_flags or [],
            user_message=(user_message or "")[:2000] or None,
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def add_summary(
        self,
        *,
        user_id: int,
        session_id: str | None,
        summary_type: str,
        summary_text: str,
    ) -> CoachSummary:
        row = CoachSummary(
            user_id=user_id,
            session_id=session_id,
            summary_type=summary_type,
            summary_text=summary_text,
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def get_today_daily_summary(self, user_id: int) -> CoachSummary | None:
        start, end = utc_day_bounds()
        result = await self.db.execute(
            select(CoachSummary)
            .where(CoachSummary.user_id == user_id)
            .where(CoachSummary.summary_type == "daily")
            .where(CoachSummary.created_at >= start)
            .where(CoachSummary.created_at < end)
            .order_by(CoachSummary.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_routing_events(
        self, limit: int = 100
    ) -> list[HeadCoachRoutingEvent]:
        result = await self.db.execute(
            select(HeadCoachRoutingEvent)
            .order_by(HeadCoachRoutingEvent.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_summaries(
        self, limit: int = 100, summary_type: str | None = None
    ) -> list[CoachSummary]:
        query = (
            select(CoachSummary).order_by(CoachSummary.created_at.desc()).limit(limit)
        )
        if summary_type:
            query = (
                select(CoachSummary)
                .where(CoachSummary.summary_type == summary_type)
                .order_by(CoachSummary.created_at.desc())
                .limit(limit)
            )
        result = await self.db.execute(query)
        return list(result.scalars().all())
