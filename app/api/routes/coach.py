"""Daily summary and admin listings for Head Coach / Summarizer."""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes.auth import get_current_user
from app.api.schemas.coach import (
    CoachSummaryResponse,
    DailySummaryResponse,
    HeadCoachRoutingEventResponse,
)
from app.db.database import get_db
from app.db.repositories.coach_events_repo import CoachEventsRepository
from app.services.session_manager import get_session_manager
from app.services.user_profile_service import UserProfileService

logger = logging.getLogger(__name__)

router = APIRouter()


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


@router.post("/summaries/daily", response_model=DailySummaryResponse)
async def generate_daily_summary(
    refresh: bool = Query(default=False),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Build today's Daily Summary via the summarizer agent and persist it."""
    from agents.summarizer import strip_daily_summary_heading
    from agents.summarizer import summarizer as summarizer_agent

    repo = CoachEventsRepository(db)
    if not refresh:
        existing = await repo.get_today_daily_summary(current_user["id"])
        if existing:
            return DailySummaryResponse(
                summary=strip_daily_summary_heading(existing.summary_text),
                generated_at=existing.created_at,
                reused=True,
            )

    profile_service = UserProfileService(db)
    try:
        profile = await profile_service.get_user_profile(current_user["id"])
    except ValueError:
        profile = {"fitness_goal": "general fitness", "fitness_level": "beginner"}

    session_mgr = get_session_manager()
    messages = await session_mgr.list_user_messages(current_user["id"])

    state = {
        "summary_kind": "daily",
        "messages": messages,
        "user_profile": {
            "name": current_user.get("name", "Athlete"),
            "goal": profile.get("fitness_goal", "general fitness"),
            "fitness_level": profile.get("fitness_level", "beginner"),
            "user_id": current_user["id"],
        },
    }
    summary = strip_daily_summary_heading(summarizer_agent(state))
    row = await repo.add_summary(
        user_id=current_user["id"],
        session_id=None,
        summary_type="daily",
        summary_text=summary,
    )
    return DailySummaryResponse(
        summary=row.summary_text,
        generated_at=row.created_at or datetime.now(UTC),
        reused=False,
    )


@router.get(
    "/admin/head-coach-routes",
    response_model=list[HeadCoachRoutingEventResponse],
)
async def list_head_coach_routes(
    limit: int = Query(default=100, ge=1, le=500),
    _: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    repo = CoachEventsRepository(db)
    return await repo.list_routing_events(limit=limit)


@router.get("/admin/summaries", response_model=list[CoachSummaryResponse])
async def list_summaries(
    limit: int = Query(default=100, ge=1, le=500),
    summary_type: str | None = Query(default=None),
    _: dict = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    repo = CoachEventsRepository(db)
    return await repo.list_summaries(limit=limit, summary_type=summary_type)
